"""Cable-free connection to the iPhone over the local network.

iOS 17+ announces a RemotePairing service over Bonjour on Wi-Fi. A host that
holds a RemotePairing record for the phone can open the same no-admin
userspace tunnel used for USB, just over the network. The record is created
once over USB, where the existing Trust makes it promptless.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import socket
import struct
from typing import Optional

_VPN_ADAPTER = re.compile(
    r"tap|tun|wintun|wireguard|nordlynx|nordvpn|openvpn|proton|surfshark|expressvpn|"
    r"hyper-v|vethernet|bluetooth|pseudo|zerotier|tailscale|hamachi|ipvanish",
    re.I,
)
_WIFIDIRECT_ADAPTER = re.compile(r"wi-?fi direct", re.I)

WIFI_NOT_FOUND_HINT = (
    "The iPhone was not found on the network. Put the PC and the iPhone on the same Wi-Fi, "
    "keep the iPhone unlocked, and set that Wi-Fi to Private in Windows settings. "
    "If a VPN is on, disconnect it or allow local network traffic — VPNs often block Bonjour."
)

WIFI_NOT_FOUND_NO_ADS = (
    "Pane did not see the iPhone's Wi-Fi pairing broadcast on the LAN. "
    "Unplug the USB cable, unlock the iPhone, and confirm it is on Wi-Fi (not cellular only). "
    "Some routers isolate wireless clients — disable AP/client isolation, or mirror over USB."
)

WIFI_MULTICAST_BLOCKED = (
    "Multicast DNS (UDP port 5353) does not appear to work on this PC, so Wi-Fi discovery cannot run. "
    "Allow Python/Pane through Windows Firewall on Private networks, or use USB mirroring."
)

BONJOUR_TIMEOUT = 12.0
_MDNS_GROUP = "224.0.0.251"
_MDNS_PORT = 5353
_bonjour_patched = False


def _adapter_label(adapter: object) -> str:
    names = []
    for key in ("nice_name", "name", "friendly_name"):
        value = getattr(adapter, key, None)
        if value:
            names.append(str(value))
    return " ".join(names)


def _private_ipv4(adapter: object) -> bool:
    for ip in getattr(adapter, "ips", ()) or ():
        addr = getattr(ip, "ip", None)
        if not isinstance(addr, str):
            continue
        if addr.startswith(("10.", "192.168.")):
            return True
        if addr.startswith("172."):
            parts = addr.split(".")
            if len(parts) >= 2 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
                return True
    return False


def _skip_adapter(adapter: object) -> bool:
    label = _adapter_label(adapter)
    if _VPN_ADAPTER.search(label):
        return True
    # Windows mobile hotspot is a Wi-Fi Direct adapter with a private subnet
    # (usually 192.168.137.0/24). Keep that. Skip Miracast-style adapters that
    # have no address an iPhone can join.
    if _WIFIDIRECT_ADAPTER.search(label):
        return not _private_ipv4(adapter)
    return False


def _local_ipv4() -> list[str]:
    try:
        import ifaddr
    except ImportError:
        return []
    ranked: list[tuple[int, str]] = []
    for adapter in ifaddr.get_adapters():
        if _skip_adapter(adapter):
            continue
        label = _adapter_label(adapter).lower()
        on_wifi = any(token in label for token in ("wi-fi", "wifi", "wlan", "802.11"))
        for ip in adapter.ips:
            if not isinstance(ip.ip, str) or ip.ip.startswith("127."):
                continue
            addr = ip.ip
            if addr.startswith("169.254."):
                score = 10 + (20 if on_wifi else 0)
            elif addr.startswith(("10.", "192.168.", "172.")):
                score = 100 + (30 if on_wifi else 0)
            else:
                score = 50 + (20 if on_wifi else 0)
            ranked.append((score, addr))
    if not ranked:
        return []
    ranked.sort(key=lambda item: -item[0])
    found: list[str] = []
    seen: set[str] = set()
    for _, addr in ranked:
        if addr in seen:
            continue
        seen.add(addr)
        found.append(addr)
    return found


def remote_pairing_record_ok(udid: str) -> bool:
    """Return whether the saved RemotePairing record can be matched over Bonjour."""
    try:
        from pymobiledevice3.pair_records import iter_remote_pair_records_by_identifier
        from pymobiledevice3.remote.tunnel_service import PEER_ALT_IRK_KEY
    except ImportError:
        return False
    for identifier, _, record in iter_remote_pair_records_by_identifier():
        if identifier == udid:
            return isinstance(record, dict) and record.get(PEER_ALT_IRK_KEY) is not None
    return False


async def wifi_discovery_snapshot(timeout: float = 4.0) -> dict:
    """Quick LAN probe for troubleshooting Wi-Fi discovery."""
    from pymobiledevice3 import bonjour

    _patch_bonjour()
    sent, errors = await bonjour.probe_multicast()
    blocked = bonjour.is_multicast_blocked(sent, errors)
    seen = 0
    async for _ in bonjour.iter_browse_remotepairing(timeout=timeout):
        seen += 1
    return {
        "localAddresses": _local_ipv4(),
        "multicastBlocked": blocked,
        "remotepairingAdvertisements": seen,
    }


def _patch_bonjour() -> None:
    """Browse mDNS on every IPv4 adapter, not just Windows' default one.

    pymobiledevice3 joins the mDNS group and sends its queries on the default
    interface only. With several adapters (Wi-Fi, Bluetooth, the iPhone's USB
    hotspot, virtual adapters) that is rarely the Wi-Fi, so the phone's
    announcement is never seen.
    """
    global _bonjour_patched
    if _bonjour_patched:
        return
    from pymobiledevice3 import bonjour

    original_bind = bonjour._bind_ipv4
    original_send = bonjour._send_query_all

    async def bind_ipv4(queue):
        transport, sock = await original_bind(queue)
        group = socket.inet_aton(_MDNS_GROUP)
        for ip in _local_ipv4():
            with contextlib.suppress(OSError):
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, struct.pack("=4s4s", group, socket.inet_aton(ip)))
        return transport, sock

    async def send_query_all(transports, pkt, *args, **kwargs):
        sent = await original_send(transports, pkt, *args, **kwargs)
        for _, sock in transports:
            if sock.family != socket.AF_INET:
                continue
            # Queries must leave from port 5353 so replies come back to the
            # listening socket; send synchronously so each one uses its own
            # egress interface.
            for ip in _local_ipv4():
                with contextlib.suppress(OSError):
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ip))
                    sock.sendto(pkt, (_MDNS_GROUP, _MDNS_PORT))
                    sent += 1
        return sent

    bonjour._bind_ipv4 = bind_ipv4
    bonjour._send_query_all = send_query_all
    _bonjour_patched = True


def wifi_paired_udids() -> list[str]:
    try:
        from pymobiledevice3.pair_records import iter_remote_paired_identifiers

        return sorted(set(iter_remote_paired_identifiers()))
    except Exception:
        return []


def pair_for_wifi(udid: str) -> dict:
    """Write the RemotePairing record over the trusted USB link."""

    async def pair() -> None:
        from pymobiledevice3.exceptions import RemotePairingCompletedError
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.remote.tunnel_service import RemotePairingLockdownService

        lockdown = await create_using_usbmux(serial=udid)
        service = await RemotePairingLockdownService.create(lockdown)
        try:
            await service.connect(autopair=True)
        except RemotePairingCompletedError:
            pass
        finally:
            await service.close()
            await lockdown.close()

    try:
        asyncio.run(pair())
    except Exception as error:
        return {"ok": False, "error": f"Wi-Fi setup needs the cable once: {error}"}
    return {"ok": udid in wifi_paired_udids(), "paired": wifi_paired_udids()}


async def _wifi_provider(serial: Optional[str], autopair: bool, remotepairing_fallback: bool = True):
    from pymobiledevice3.remote import tunnel_service

    _patch_bonjour()
    services = await tunnel_service.get_remote_pairing_tunnel_services(
        udid=serial, bonjour_timeout=BONJOUR_TIMEOUT
    )
    if not services:
        if serial and not remote_pairing_record_ok(serial):
            raise WifiNotFoundError(
                "This PC's Wi-Fi pairing record is outdated. Plug in the cable, tap Trust, "
                "and press Set up Wi-Fi again."
            )
        probe = await wifi_discovery_snapshot(timeout=min(5.0, BONJOUR_TIMEOUT))
        if probe["multicastBlocked"]:
            raise WifiNotFoundError(f"{WIFI_NOT_FOUND_HINT} {WIFI_MULTICAST_BLOCKED}")
        if probe["remotepairingAdvertisements"] == 0:
            raise WifiNotFoundError(f"{WIFI_NOT_FOUND_HINT} {WIFI_NOT_FOUND_NO_ADS}")
        raise WifiNotFoundError(WIFI_NOT_FOUND_HINT)
    for extra in services[1:]:
        await extra.close()
    # pymobiledevice3 11.59+ expects a TunnelProvider. Older releases used a
    # plain (service, lockdown) tuple.
    try:
        from pymobiledevice3.remote.userspace_tunnel import TunnelProvider
    except ImportError:
        return services[0], None
    return TunnelProvider(services[0])


class WifiNotFoundError(RuntimeError):
    pass


def wifi_tunnel(udid: str):
    """An RSD tunnel to ``udid`` over Wi-Fi, used like ``PreferredRsdTunnel``."""
    from pymobiledevice3.remote import userspace_tunnel

    class WifiRsdTunnel(userspace_tunnel.UserspaceRsdTunnel):
        # The base class always starts from USB (usbmux); swap in the network
        # provider for the duration of this tunnel's setup only.
        async def _aopen_locked(self):
            original = userspace_tunnel._create_no_root_tunnel_provider
            userspace_tunnel._create_no_root_tunnel_provider = _wifi_provider
            try:
                return await super()._aopen_locked()
            finally:
                userspace_tunnel._create_no_root_tunnel_provider = original

    return WifiRsdTunnel(serial=udid, autopair=False)
