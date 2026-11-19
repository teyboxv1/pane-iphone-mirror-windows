"""Unit tests for Pane handset helpers (stdlib only)."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from handset.airplay import airplay_status
from handset.screen import _parse_ios_major
from handset.wifi import _skip_adapter
from handset.window import ALLOWED_ACTIONS, window_action


class ParseIosMajorTests(unittest.TestCase):
    def test_major(self) -> None:
        self.assertEqual(_parse_ios_major("26.5.2"), 26)
        self.assertEqual(_parse_ios_major("27.0.1"), 27)

    def test_invalid(self) -> None:
        self.assertIsNone(_parse_ios_major(None))
        self.assertIsNone(_parse_ios_major("beta"))


class VpnAdapterTests(unittest.TestCase):
    def test_skip_wireguard(self) -> None:
        adapter = SimpleNamespace(nice_name="WireGuard Tunnel", name="wg0")
        self.assertTrue(_skip_adapter(adapter))

    def test_keep_wifi(self) -> None:
        adapter = SimpleNamespace(nice_name="Wi-Fi", name="wlan0")
        self.assertFalse(_skip_adapter(adapter))


class BonjourForwardTests(unittest.IsolatedAsyncioTestCase):
    async def test_extra_positional_forwarded(self) -> None:
        seen: list[tuple] = []

        async def original(transports, pkt, *args, **kwargs):
            seen.append((transports, pkt, args, kwargs))
            return 3

        async def wrapper(transports, pkt, *args, **kwargs):
            return await original(transports, pkt, *args, **kwargs)

        result = await wrapper([], b"q", "extra")
        self.assertEqual(result, 3)
        self.assertEqual(seen[0][2], ("extra",))


class AirplayTests(unittest.TestCase):
    def test_status_without_binary(self) -> None:
        status = airplay_status()
        self.assertIn("available", status)
        self.assertIn("connected", status)
        self.assertFalse(status["available"])
        self.assertFalse(status["connected"])


class WindowActionTests(unittest.TestCase):
    def test_unknown_action(self) -> None:
        self.assertFalse(window_action("maximize"))

    def test_allowed_set(self) -> None:
        self.assertIn("resize", ALLOWED_ACTIONS)
        self.assertNotIn("maximize", ALLOWED_ACTIONS)


if __name__ == "__main__":
    unittest.main()