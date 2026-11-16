"""Cable-free connection to the iPhone over the local network.

iOS 17+ announces a RemotePairing service over Bonjour on Wi-Fi. A host that
holds a RemotePairing record for the phone can open the same no-admin
userspace tunnel used for USB, just over the network. The record is created
once over USB, where the existing Trust makes it promptless.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import struct
from typing import Optional

BONJOUR_TIMEOUT = 8.0
_MDNS_GROUP = "224.0.0.251"
_MDNS_PORT = 5353
_bonjour_patched = False


def _local_ipv4() -> list[str]:
    try:
        import ifaddr
    except ImportError:
        return []
    found = []
    for adapter in ifaddr.get_adapters():
        for ip in adapter.ips:
            if isinstance(ip.ip, str) and not ip.ip.startswith("127."):
                found.append(ip.ip)
    return found


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
        raise WifiNotFoundError(
            "The iPhone was not found on the network. Put the PC and the iPhone on the same Wi-Fi, "
            "keep the iPhone unlocked, and set that Wi-Fi to Private in Windows settings."
        )
    for extra in services[1:]:
        await extra.close()
    return services[0], None


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
