# Changelog

All notable changes to Pane are documented here.

## [1.0.1] - 2026-11-17

Windows build: Pane 1.0.1.

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

---

## [1.0.0-custom] - 2026-11-16

### Sửa lỗi (Bug Fixes)
- **Wi-Fi Discovery (`handset/wifi.py`)**: Sửa lỗi `TypeError: _patch_bonjour.<locals>.send_query_all() takes 2 positional arguments but 3 were given` bằng cách nhận `*args, **kwargs` và chuyển tiếp cho `pymobiledevice3.bonjour._send_query_all`.

---

## [1.0.0-custom] - 2026-11-12

### Tính năng mới (Features)
- **Tích hợp AirPlay Audio Receiver (`handset/airplay.py`, `handset/bin/shairport.exe`)**:
  - Tự động quản lý tiến trình máy chủ nhận AirPlay Audio portable khi khởi chạy và dọn dẹp khi tắt app.
  - Thêm popup hướng dẫn kết nối âm thanh trong giao diện điều khiển khi bấm vào icon loa.
  - Hiển thị trạng thái kết nối âm thanh trực tiếp (đang kết nối / ngắt kết nối).
- **Chế độ cửa sổ thu gọn & Electron Borderless**:
  - Hỗ trợ chạy chế độ compact không viền, nền trong suốt.
  - Tích hợp các nút điều khiển thu nhỏ, phóng to, đóng cửa sổ riêng.
- **Đóng gói (Packaging)**:
  - Cập nhật file cấu hình PyInstaller `packaging/pane.spec` để đóng gói tự động `shairport.exe` và các tệp giao diện web tĩnh vào tệp `Pane.exe`.
