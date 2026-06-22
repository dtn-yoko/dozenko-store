# Test Log — Dozenko End-to-End

## Bug 1: Website live không kết nối CRM (CRITICAL)
- **Triệu chứng:** Form waitlist, chatbot, nút mua hàng trên dozenko.io.vn không hoạt động.
- **Nguyên nhân:** `index.html` có `window.DOZENKO_CRM_API_BASE = ''` (rỗng) trên production.
- **Fix:** Set lại thành `https://dozenko-crm.onrender.com`. Đã deploy qua GitHub Pages.
- **Trạng thái:** ✅ Đã fix, verify live.

## Bug 2: brain.db mất dữ liệu mỗi khi Render restart
- **Triệu chứng:** Customer/order tạo trong runtime biến mất hoàn toàn sau khi Render deploy lại hoặc spin-down/wake.
- **Nguyên nhân:** SQLite file nằm trên filesystem tạm (ephemeral) của Render free tier — mỗi lần restart, filesystem reset về đúng bản trong git repo.
- **Fix:** Free tier không có Persistent Disk, nên dùng GitHub branch `db-backup` làm nơi lưu backup: app tự pull bản backup mới nhất lúc khởi động, tự push backup sau mỗi lần tạo customer/order/confirm-payment + định kỳ 3 phút. Cần `GITHUB_TOKEN` + `GITHUB_REPO` set trong Render Environment.
- **Trạng thái:** ✅ Đã fix, verify qua Manual Deploy — data sống sót qua restart.

## Bug 3: SePay không tự cập nhật trạng thái đơn hàng 'success'
- **Triệu chứng:** Chuyển khoản thật thành công (xác nhận trên app Techcombank, đúng số tài khoản + nội dung ORDx) nhưng SePay không ghi nhận giao dịch, webhook không bắn, đơn hàng vẫn 'pending'.
- **Nguyên nhân:** Lỗi đồng bộ giữa SePay ↔ Vietinbank (tài khoản hiện "Đã kết nối API" nhưng số dư không cập nhật giao dịch mới) — không phải lỗi code CRM.
- **Workaround tạm:** Dùng nút "Xác nhận thanh toán" trong /admin để admin tự xác nhận tay khi tự động hóa lỗi.
- **Trạng thái:** ⚠️ CHƯA FIX — cần liên hệ Support SePay hoặc kết nối lại tài khoản ngân hàng. Không phải lỗi sửa được bằng code.

## Bug 4: "database is locked" khi nhiều request ghi DB đồng thời
- **Triệu chứng:** `DELETE /api/customers/<id>` (và có thể các write khác) trả về 500, log server: `sqlite3.OperationalError: database is locked`.
- **Nguyên nhân:** Nhiều connection SQLite (APScheduler email job, GitHub backup thread, request API) ghi đồng thời, không có busy timeout nên SQLite từ chối ngay lập tức.
- **Fix (đợt 1):** Thêm `timeout=30` + `PRAGMA busy_timeout` + WAL mode vào `get_connection()`, đổi backup sang dùng SQLite online backup API (snapshot nhất quán) thay vì đọc file thô.
- **Trạng thái:** ⚠️ ĐANG XỬ LÝ — sau fix đợt 1, lỗi vẫn còn nhưng thời gian chờ trước khi lỗi đã tăng đúng theo timeout cấu hình (30s), cho thấy có 1 connection nào đó giữ khóa write liên tục không nhả (>30s), cần điều tra thêm qua log Render.
