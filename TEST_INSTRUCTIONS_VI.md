# Hướng Dẫn Test Email Sequence System

## 🎯 Cách Test Hệ Thống

### Phương Pháp 1: Dùng Form Trên Website (Phương Pháp Chính)

1. **Mở website**: Vào trang chính của Dozenko
2. **Tìm form đơn hàng/đăng ký**: Scroll xuống tìm form (section "Đơn Đặt Hàng")
3. **Điền thông tin**:
   - Tên: Nhập tên của bạn (hoặc tên test)
   - Số điện thoại: `0987654321` (hoặc số bất kỳ)
   - **Email**: ⚠️ **QUAN TRỌNG** - Nhập email với `+test`
     - Ví dụ: `tenmình+test@gmail.com`
     - Hoặc: `email.của.bạn+test@gmail.com`
     - Hoặc bất kỳ email nào + `+test`
4. **Chọn màu**: Tích chọn ít nhất 1 màu
5. **Điền địa chỉ**: Nhập địa chỉ giao hàng (test có thể random)
6. **Click nút "Đặt Hàng"**: Gửi form
7. **Kiểm tra hộp thư**: 

### ✅ Kết Quả Dự Kiến Khi Dùng +test

**Bạn sẽ nhận được 3 email từ `hi@dozenko.io.vn`**:

#### Email 1 (Ngay lập tức)
- **Tiêu đề**: "Chào bạn! Chúng mình nhận được yêu cầu của bạn 🌸"
- **Nội dung**: Cảm ơn đã đăng ký, thông tin sản phẩm cơ bản
- **Thời gian**: Vài giây sau khi submit form

#### Email 2 (Vẫn ngay lập tức - vì là test)
- **Tiêu đề**: "Khám phá bộ sưu tập thảm hoa Dozenko 🎨"
- **Nội dung**: Chi tiết sản phẩm, kích thước, giá cả, combo
- **CTA**: Nút "Xem Bộ Sưu Tập & Đặt Hàng"
- **Thời gian**: Vài giây sau Email 1

#### Email 3 (Vẫn ngay lập tức - vì là test)
- **Tiêu đề**: "Đặt hàng thảm Dozenko ngay - Hàng có hạn! ⚡"
- **Nội dung**: Giới hạn thời gian, testimonials, khuyến mãi
- **CTA**: Nút "ĐẶT HÀNG NGAY - HÀNG CÓ HẠN! ⚡"
- **Thời gian**: Vài giây sau Email 2

### 🔍 Xác Minh Chi Tiết

Kiểm tra từng email để confirm:

- ✅ **Địa chỉ gửi**: Phải là `hi@dozenko.io.vn` (KHÔNG phải @resend.dev)
- ✅ **Tên người gửi**: "Đội Dozenko" hoặc tương tự
- ✅ **Nội dung HTML**: Phải được format đẹp, không phải text thô
- ✅ **Nút CTA**: Các nút màu xanh/đỏ có thể click
- ✅ **Email đến**: Inbox của bạn (email+test@domain vẫn đi vào hộp thư bình thường)

### Phương Pháp 2: Nếu Muốn Test Chế Độ Thường (Không +test)

Điền form **KHÔNG** có `+test` trong email:
- Email 1 sẽ được gửi ngay lập tức
- Email 2 sẽ được gửi tự động sau 2 ngày
- Email 3 sẽ được gửi tự động sau 3 ngày (1 ngày sau Email 2)

Cách kiểm tra:
```bash
# Xem trạng thái email sequence
curl http://localhost:5000/api/email-sequences
```

Sẽ thấy:
```json
{
  "email1_sent": 1,        // Đã gửi
  "email1_sent_at": "2026-06-21T09:30:00Z",
  "email2_sent": 0,        // Chưa gửi
  "email2_scheduled_at": "2026-06-23T09:30:00Z",  // Sẽ gửi ngày 23/6
  "email3_sent": 0,
  "email3_scheduled_at": "2026-06-24T09:30:00Z"   // Sẽ gửi ngày 24/6
}
```

### ⚠️ Lưu Ý Về +test Email

- Gmail/Outlook/Yahoo: Tất cả email dạng `account+anything@domain` đều được gửi vào hộp thư chính của `account@domain`
- Không cần tạo email mới
- Test email vẫn hoạt động bình thường như email thực

### Ví Dụ Cụ Thể

Nếu email thực của bạn là: `nguyenvana@gmail.com`

**Dùng +test**: `nguyenvana+test@gmail.com`
- Email vẫn đi vào hộp thư của `nguyenvana@gmail.com`
- Có thể thấy trong TO: `nguyenvana+test@gmail.com`
- Gửi bởi: `hi@dozenko.io.vn` ✅

### Bị Lỗi?

Nếu:
- ❌ Email không tới
- ❌ Địa chỉ gửi là @resend.dev thay vì @dozenko.io.vn
- ❌ Email không được format đẹp

→ **Làm này**: Copy error message từ terminal/logs → paste vào AI → nói "bị lỗi này, fix giúp tôi"

### Kiểm Tra Logs

Khi app.py đang chạy, hãy xem terminal:
```
# Thành công:
✅ Email sequence scheduler started

# Khi gửi email:
POST /api/customers
200 OK
```

Nếu có lỗi, sẽ thấy traceback chi tiết.

---

## 📊 Tóm Tắt Test Cases

| Kịch Bản | Email | Kết Quả |
|---------|-------|--------|
| **Test Mode** | `user+test@domain` | 3 emails gửi ngay lập tức ✅ |
| **Normal Mode** | `user@domain` | Email 1 ngay, 2&3 lên lịch ✅ |
| **Check Status** | GET `/api/email-sequences` | Xem trạng thái tất cả sequences |
| **Admin View** | GET `/api/email-sequences/<id>` | Xem chi tiết 1 sequence |

---

**Hệ thống đã sẵn sàng để test! 🚀**
