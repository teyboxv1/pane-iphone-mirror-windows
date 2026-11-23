"""Pane's display geometry adapter for the pymobiledevice3 screen stream."""

from __future__ import annotations

import json

from pymobiledevice3.remote.core_device.device_info import display_rotation
from pymobiledevice3.remote.core_device.hevc_rps import parse_sps
from pymobiledevice3.remote.core_device.screen_stream import ScreenStreamServer, _hevc_rbsp


class PaneStreamServer(ScreenStreamServer):
    _touch_rotation = 0

    def _apply_display(self, display: dict) -> bool:
        native = display_rotation({"currentOrientation": display.get("nativeOrientation")})
        self._touch_rotation = (native + display_rotation(display)) % 360
        return super()._apply_display(display)

    def _decoder_config(self, description_b64: str) -> dict:
        config = super()._decoder_config(description_b64)
        if self._sps_nal:
            try:
                sps = parse_sps(_hevc_rbsp(self._sps_nal))
            except (IndexError, ValueError):
                return config
            config["codedWidth"] = sps.pic_width_in_luma_samples
            config["codedHeight"] = sps.pic_height_in_luma_samples
        return config

    async def _handle_touch(self, body: bytes) -> tuple[int, bytes]:
        # Pane sends upright display coordinates, not raw digitizer coordinates.
        rotation = self._touch_rotation
        if rotation:
            try:
                data = json.loads(body)
                x, y = int(data["x"]), int(data["y"])
            except (KeyError, TypeError, ValueError):
                return await super()._handle_touch(body)
            if rotation == 90:
                x, y = y, 65535 - x
            elif rotation == 180:
                x, y = 65535 - x, 65535 - y
            elif rotation == 270:
                x, y = 65535 - y, x
            data["x"], data["y"] = x, y
            body = json.dumps(data).encode()
        return await super()._handle_touch(body)
