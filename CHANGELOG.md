# Nhật ký thay đổi (Changelog)

Chi tiết các cập nhật và tính năng mới được bổ sung vào dự án Pane:

---

## [Unreleased] - 2026-11-16

### Sửa lỗi (Bug Fixes)
- **Wi-Fi Discovery (`handset/wifi.py`)**: Sửa lỗi `TypeError: _patch_bonjour.<locals>.send_query_all() takes 2 positional arguments but 3 were given` bằng cách nhận `*args, **kwargs` và chuyển tiếp cho `pymobiledevice3.bonjour._send_query_all`.

---

## [Update] - 2026-11-12

### Tính năng mới (Features)
- **Tích hợp AirPlay Audio Receiver (`handset/airplay.py`, `handset/bin/shairport.exe`)**:
  - Tự động quản lý tiến trình máy chủ nhận AirPlay Audio portable khi khởi chạy và dọn dẹp khi tắt app.
  - Thêm popup hướng dẫn kết nối âm thanh trong giao diện điều khiển khi bấm vào icon loa.
  - Hiển thị trạng thái kết nối âm thanh trực tiếp (đang kết nối / ngắt kết nối).
  - Tự động bỏ qua các gói tin rỗng/heartbeat và tự khôi phục codec khi gặp lỗi xử lý âm thanh.
- **Chế độ cửa sổ thu gọn & Electron Borderless**:
  - Hỗ trợ chạy chế độ compact không viền, nền trong suốt.
  - Tích hợp các nút điều khiển thu nhỏ, phóng to, đóng cửa sổ riêng.

### Đóng gói (Packaging)
- Cập nhật file cấu hình PyInstaller `packaging/pane.spec` để đóng gói tự động `shairport.exe` và các tệp giao diện web tĩnh vào tệp `Pane.exe`.
