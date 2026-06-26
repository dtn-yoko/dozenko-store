# MCP function draft — Dozenko CRM qua Telegram

3 function được chọn để build trước. Dựa trên `app.py` hiện có: bảng `products`
(tồn kho), `customers`, `orders` (trạng thái pending/success/failed/cancelled),
`webhook_events` (SePay). Mỗi function map trực tiếp vào endpoint `/api/*` đã
có sẵn — MCP server chỉ gọi qua HTTP, không cần sửa backend.

---

## 1. get_daily_summary

- **Input:** `date` (string, ISO `YYYY-MM-DD`, optional — default hôm nay)
- **Output:** số đơn mới, tổng tiền theo trạng thái (pending/success/failed),
  số khách mới, sản phẩm bán nhiều nhất trong ngày
- **Tình huống dùng:** sáng/tối hỏi "hôm nay bán được bao nhiêu" mà không cần mở `/admin`.
- **Độ ưu tiên:** 5
- **Nguồn dữ liệu:** `GET /api/orders` + `GET /api/customers` (lọc theo `order_date`/`signup_date` ở phía MCP, vì API hiện chưa filter theo ngày)
- **Ví dụ câu nhắn Telegram sẽ trigger:**
  - "hôm nay bán được bao nhiêu rồi"
  - "tổng kết hôm nay đi"
  - "doanh thu ngày 26/6 thế nào"
  - "có bao nhiêu đơn mới hôm nay"

## 2. confirm_order_payment

- **Input:** `order_id` (int), hoặc `customer_phone` + `amount` (string/float) nếu chưa biết order_id
- **Output:** trạng thái đơn sau khi confirm (`success`), tên khách, sản phẩm, số tiền
- **Tình huống dùng:** khách chuyển khoản nhưng webhook SePay không bắt được (sai nội dung CK) — chủ shop tự confirm tay ngay trên Telegram thay vì mở `/admin`.
- **Độ ưu tiên:** 5
- **Nguồn dữ liệu:** `POST /api/orders/<id>/confirm-payment` (đã có sẵn, đúng mục đích)
- **Ví dụ câu nhắn Telegram sẽ trigger:**
  - "xác nhận thanh toán đơn #45"
  - "khách 0912345678 vừa chuyển khoản 300k rồi, confirm giúp"
  - "đơn của chị Hà đã thanh toán, đánh dấu thành công"
  - "duyệt đơn 45 đi, tiền vào rồi nhưng hệ thống chưa tự bắt"

## 3. check_low_stock

- **Input:** `threshold` (int, optional, default 5)
- **Output:** danh sách sản phẩm `type=physical` có `quantity <= threshold`, kèm tên + số lượng còn
- **Tình huống dùng:** kiểm tra nhanh "còn thảm màu nào sắp hết để nhập thêm" trước khi đăng bài bán tiếp.
- **Độ ưu tiên:** 4
- **Nguồn dữ liệu:** `GET /api/products` (lọc `quantity` ở phía MCP)
- **Ví dụ câu nhắn Telegram sẽ trigger:**
  - "sản phẩm nào sắp hết hàng"
  - "kiểm tra tồn kho giúp"
  - "còn dưới 3 cái thì báo tôi"
  - "thảm màu xanh còn bao nhiêu"

## 4. update_hero_text (thêm sau, ngoài 3 cái ban đầu)

- **Input:** `text` (string), `field` (string: `hero_title` hoặc `hero_subtitle`, default `hero_title`)
- **Output:** nội dung mới đã lưu + thời gian cập nhật
- **Tình huống dùng:** đổi tiêu đề/mô tả trang chủ ngay qua Telegram khi chạy campaign (ví dụ "Flash sale cuối tuần 30%") mà không cần sửa code/deploy lại.
- **Độ ưu tiên:** bổ sung theo yêu cầu thực tế phát sinh khi test MCP qua goClaw
- **Nguồn dữ liệu:** bảng mới `site_content` (key-value) trong `brain.db` + `PUT /api/content/<key>`. Trang chủ (`index.html`/`script.js`) load override này lúc page load — không cần deploy lại để thấy thay đổi.
