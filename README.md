# VPN Proxy Gateway

> Biến các gói VPN trả phí (NordVPN, ExpressVPN, Surfshark, ProtonVPN, PIA,...) thành các SOCKS5/HTTP Proxy có xác thực, tích hợp Kill-switch bảo vệ IP thật và tự động xoay server.

## ✨ Tính năng chính

- **Đa nhà cung cấp:** Hỗ trợ NordVPN (WireGuard & OpenVPN), ExpressVPN, Surfshark, ProtonVPN, Private Internet Access,... theo mô hình Adapter Plugin.
- **SOCKS5 & HTTP/HTTPS:** Mỗi tunnel cung cấp đồng thời 2 port proxy với username & password sinh ngẫu nhiên hoặc tùy chỉnh.
- **Kill-Switch 2 lớp:** Ngăn chặn rò rỉ IP thật ra Internet khi kết nối VPN bị ngắt đột ngột.
- **Tự động xoay server:** Xoay IP theo lịch (interval), biểu thức Cron hoặc gọi API REST (`/api/tunnels/{id}/rotate`).
- **Giám sát băng thông & trạng thái:** Thu thập chỉ số từ GOST và kiểm tra sức khỏe proxy định kỳ.
- **Bảo vệ giới hạn thiết bị (Quota):** Đặt giới hạn kết nối theo từng tài khoản VPN để không vượt quota gói cước.

## 🛠️ Cài đặt & Triển khai nhanh với Docker

```bash
cd deploy
cp .env.example .env
# Chỉnh sửa VPG_MASTER_KEY, VPG_ADMIN_PASSWORD trong file .env
docker compose up -d
```

Truy cập API Swagger tại: `http://localhost:8000/docs`
