# Đối Soát Số Liệu Thật — Dozenko (cập nhật 22/06/2026)

> Lấy trực tiếp từ brain.db qua API live (https://dozenko-crm.onrender.com), đã loại trừ data test
> (các customer/order tạo ra trong lúc debug bug "database is locked" hôm nay, không phải khách thật).

## 1. Khách hàng (customers / waitlist)
- **Tổng số khách hàng thật: 3**
  1. Nguyễn Văn Tuấn — 0903352523
  2. Trần Thị Bưởi — 0905875586
  3. Lê Thị Hạnh — 0912345678

## 2. Đơn hàng (orders)
- **Tổng số đơn: 4**
- **Số đơn trạng thái 'success': 4 / 4** (100%)
- Toàn bộ 4 đơn đều của khách Lê Thị Hạnh, sản phẩm "Combo 4 Tấm Thảm (Tùy Chọn Màu)", 840.000đ/đơn.

## 3. Doanh thu thật đã nhận (chỉ tính đơn 'success')
- **Tổng doanh thu: 3.360.000đ**

## 4. Bài đăng 7 ngày qua (theo brain_score.md)
- **Đã điền nhật ký đủ nội dung: 3/7 ngày** (Ngày 1, 2, 3)
- Ngày 4-7: còn để trống (chưa điền điểm giống giọng / phản hồi / nhận xét)
- Điểm giống giọng brand voice: Ngày 1 = 7/10, Ngày 2 = 8/10, Ngày 3 = 8/10 (xu hướng tăng)

## Ghi chú quan trọng
- Số liệu trên là **data thật duy nhất tồn tại** tính đến thời điểm này — toàn bộ là dữ liệu seed/gốc từ trước (18/06), **chưa có khách/đơn hàng thật mới nào** phát sinh từ khi launch đến hôm nay (22/06).
- Trong lúc debug hôm nay phát hiện bug nghiêm trọng: brain.db từng bị mất dữ liệu mỗi lần Render restart (đã fix bằng GitHub-backup), và bug "database is locked" khi ghi đồng thời (đang tiếp tục xử lý, xem test_log.md).
