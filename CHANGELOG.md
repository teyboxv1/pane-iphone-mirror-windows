# Changelog

## 2026-11-17

### Requirements

- Live video requires **iOS / iPadOS 27 or newer**. iOS 26 and older can connect, but the phone does not send picture frames.
- The README states that minimum in the prerequisites.

### Fixes

- The phone frame fits the window instead of being stuck at a tall minimum height, so the bottom of the screen is not clipped.
- Landscape video, and the rotate buttons, turn the phone frame with the picture.
- Wi-Fi discovery skips VPN and virtual adapters, prefers the real Wi-Fi address, and explains when the iPhone is not broadcasting or is still on the USB cable.
- Bonjour queries forward extra arguments so newer pymobiledevice3 does not raise `TypeError` on `send_query_all`.
- The local UI server speaks HTTP/1.1 and returns a JSON error if a page request fails.

### Added

- Optional AirPlay audio. If `handset/bin/shairport.exe` (Shairport4w, GPL-3.0) is present, Pane starts it as "Pane Audio" and shows connection status. A missing binary does not stop the app. See `handset/bin/NOTICE.txt`.
- Compact window layout, with minimize, close, drag, and resize through the Chrome or Edge app window.
