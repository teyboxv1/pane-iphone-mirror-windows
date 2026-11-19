"""Launch and supervise the video stream and input bridge.

Pane delegates the actual HEVC stream and WebCodecs decoding to
pymobiledevice3's ScreenStreamServer (same mechanism as Xcode's Device Hub).
This module keeps the subprocess / task alive and provides a single endpoint
for the UI to check status and stop/restart mirroring.
"""

from __future__ import annotations

import asyncio
import http.client
import threading

from handset.device import developer_mode_enabled, product_version
from handset.mux import MuxError, list_devices
from handset.wifi import wifi_paired_udids, wifi_tunnel

DEVELOPER_MODE_MESSAGE = (
    "Developer Mode is not enabled on this iPhone. Open Settings -> Privacy & Security -> "
    "Developer Mode, turn it on, and restart the phone. If the computer is trusted, you can "
    "unlock it, tap Turn On, then press Show screen again."
)

MIN_IOS_MAJOR_FOR_VIDEO = 27

IOS_VIDEO_VERSION_MESSAGE = (
    "Live video mirroring needs iOS 27 or later. This iPhone does not send a display video "
    "stream on older iOS — control can still work, but the preview stays black. Update to iOS 27+ "
    "for a picture."
)

VIEW_URL = "http://127.0.0.1:8766/"
_LOCK = threading.Lock()
_STATE = {
    "phase": "idle",
    "udid": None,
    "url": None,
    "error": None,
    "note": None,
    "transport": None,
    "productVersion": None,
    "iosMajor": None,
}


def screen_status() -> dict:
    with _LOCK:
        return dict(_STATE)


def restart_screen(udid: str | None = None) -> dict:
    chosen = (udid or "").strip() or _only_udid()
    nudged = False
    for path in ("/stream/restart", "/restart"):
        try:
            conn = http.client.HTTPConnection("127.0.0.1", 8766, timeout=1.5)
            conn.request("POST", path, body=b"", headers={})
            response = conn.getresponse()
            response.read()
            conn.close()
            nudged = True
        except OSError:
            continue
    with _LOCK:
        running = _STATE.get("phase") == "running"
    if running:
        return _set(note="Stream restarted. If the picture is still black, press Restart screen again.")
    if chosen:
        return start_screen(chosen, _STATE.get("transport") or "auto")
    return _set(error="Connect the iPhone first, then start mirroring.")


def start_screen(udid: str | None, transport: str = "auto") -> dict:
    usb = _usb_udids()
    wifi = wifi_paired_udids()
    chosen = (udid or "").strip() or _only_udid(usb, wifi, transport)
    if not chosen:
        if transport == "wifi":
            return _set(phase="idle", udid=None, url=None, error="Set up Wi-Fi once with the cable plugged in.")
        return _set(phase="idle", udid=None, url=None, error="Connect the iPhone first.")

    if transport == "auto" or (transport == "usb" and not usb and chosen in wifi):
        transport = "usb" if chosen in usb else "wifi"
    if transport == "usb" and chosen not in usb:
        if chosen in wifi:
            transport = "wifi"
        else:
            return _set(phase="error", udid=chosen, url=None, error="The iPhone is not on the cable. Plug it in or choose Wi-Fi.")
    if transport == "wifi" and chosen not in wifi:
        return _set(phase="error", udid=chosen, url=None, error="Set up Wi-Fi once with the cable plugged in.")
    if transport == "usb" and developer_mode_enabled(chosen) is False:
        return _set(phase="error", udid=chosen, url=None, error=DEVELOPER_MODE_MESSAGE)

    product_ver = product_version(chosen) if chosen in usb else None
    ios_major = _parse_ios_major(product_ver)

    with _LOCK:
        if _STATE["phase"] in {"starting", "running"} and _STATE["udid"] == chosen:
            return dict(_STATE)
        note = "Looking for the iPhone on Wi-Fi…" if transport == "wifi" else None
        _STATE.update(
            phase="starting",
            udid=chosen,
            url=None,
            error=None,
            note=note,
            transport=transport,
            productVersion=product_ver,
            iosMajor=ios_major,
        )
    threading.Thread(target=_run, args=(chosen, transport), name="handset-screen", daemon=True).start()
    return screen_status()


def _run(udid: str, transport: str) -> None:
    try:
        asyncio.run(_serve(udid, transport))
        _set(phase="idle", udid=udid, url=None, error="The screen stream stopped.")
    except Exception as error:
        _set(phase="error", udid=udid, url=None, error=_plain(error))


DISPLAY_SERVICE = "com.apple.coredevice.displayservice"


def _open_tunnel(udid: str, transport: str):
    if transport == "wifi":
        return wifi_tunnel(udid)
    from pymobiledevice3.remote.rsd_tunnel import PreferredRsdTunnel

    return PreferredRsdTunnel(serial=udid, autopair=True)


async def _serve(udid: str, transport: str) -> None:
    from pymobiledevice3.remote.core_device.screen_stream import ScreenStreamServer
    from pymobiledevice3.services.mobile_image_mounter import auto_mount

    for attempt in range(2):
        async with _open_tunnel(udid, transport) as rsd:
            if DISPLAY_SERVICE in (rsd.peer_info or {}).get("Services", {}):
                await _stream(rsd, udid, ScreenStreamServer)
                return
            if attempt:
                raise RuntimeError(
                    "The developer image mounted, but the iPhone still offers no display service. "
                    "Unplug it, plug it back in, and press Show screen again."
                )
            _set(note="Mounting the developer image on the iPhone. This downloads it the first time.")
            await auto_mount(rsd)


async def _stream(rsd, udid: str, ScreenStreamServer) -> None:
    from pymobiledevice3.remote.core_device.display_service import is_media_in_use_error

    server = ScreenStreamServer(
        rsd,
        port=8766,
        media_streaming_error_handler=is_media_in_use_error,
        enable_hevc=True,
    )
    _set(phase="running", udid=udid, url=VIEW_URL, error=None, note=None)
    try:
        await server.start()
    finally:
        _set(phase="idle", udid=udid, url=None, note=None)


def _usb_udids() -> list[str]:
    try:
        return [dev.serial for dev in list_devices() if getattr(dev, "connection_type", None) == "USB"]
    except MuxError:
        return []


def _parse_ios_major(version: str | None) -> int | None:
    if not version:
        return None
    token = version.strip().split("-", 1)[0].split(" ", 1)[0]
    head = token.split(".", 1)[0]
    try:
        return int(head)
    except ValueError:
        return None


def _only_udid(usb: list[str] | None = None, wifi: list[str] | None = None, transport: str = "auto") -> str | None:
    usb = _usb_udids() if usb is None else usb
    wifi = wifi_paired_udids() if wifi is None else wifi
    if transport == "usb" and usb:
        return usb[0]
    if transport == "wifi" and wifi:
        return wifi[0]
    if usb:
        return usb[0]
    if wifi:
        return wifi[0]
    return None


def _set(**values) -> dict:
    with _LOCK:
        _STATE.update(values)
        return dict(_STATE)


def _plain(error: Exception) -> str:
    text = str(error).strip() or type(error).__name__
    name = type(error).__name__
    lower = text.lower()
    if "ios 27" in lower or "screen streaming isn't possible" in lower or "does not send" in lower:
        return IOS_VIDEO_VERSION_MESSAGE
    if name == "WifiNotFoundError":
        return text
    if name in {"ConnectionFailedToUsbmuxdError", "MuxError"} or "27015" in text or "usbmux" in text.lower():
        return "Apple Mobile Device Service is not running. Install Apple Devices, reconnect the iPhone, and tap Trust."
    if name == "UserspaceTunnelUnavailableError":
        return "This phone did not open the display tunnel. It needs iOS 17.4 or later, Trust, and Developer Mode."
    if "CoreDeviceProxy" in text or name == "InvalidServiceError":
        return "The phone did not offer its display tunnel. Turn on Developer Mode, unlock the phone, and tap Trust."
    if name == "DeviceNotFoundError":
        return "The iPhone is not on the cable. Plug it in, unlock it, and press Show screen again."
    if name in {"DeveloperModeIsNotEnabledError", "DeveloperModeError"}:
        return DEVELOPER_MODE_MESSAGE
    if "PasswordProtected" in text or "locked" in text.lower():
        return "Unlock the iPhone and keep it unlocked, then press Show screen again."
    if "PairingDialog" in text or "Trust" in text:
        return "Unlock the iPhone and tap Trust, then show the screen again."
    return text
