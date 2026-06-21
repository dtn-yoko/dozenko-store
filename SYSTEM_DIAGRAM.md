# Dozenko Email Sequence System - Hệ Thống Flow

## 🎯 Quy Trình Tổng Quan

```
┌─────────────────────────────────────────────────────────────┐
│            KHÁCH HÀNG ĐIỀN FORM TRÊN WEBSITE               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │   Kiểm Tra Email Có +test?   │
        └──────────────────────────────┘
                       │
           ┌───────────┴───────────┐
           │                       │
           ▼                       ▼
    ┌─────────────┐         ┌──────────────┐
    │ CÓ +test    │         │ KHÔNG +test  │
    │ TEST MODE   │         │ NORMAL MODE  │
    └─────────────┘         └──────────────┘
           │                       │
           ▼                       ▼
    ┌─────────────┐         ┌──────────────┐
    │  Email 1    │         │   Email 1    │
    │   NGAY LẬP  │         │   NGAY LẬP   │
    │   TỨC (✅)  │         │   TỨC (✅)   │
    └─────────────┘         └──────────────┘
           │                       │
           ▼                       ▼
    ┌─────────────┐         ┌──────────────┐
    │  Email 2    │         │  Lên lịch    │
    │   NGAY LẬP  │         │  sau 2 ngày  │
    │   TỨC (✅)  │         └──────────────┘
    └─────────────┘                │
           │                       │
           ▼                       ▼ (APScheduler)
    ┌─────────────┐         ┌──────────────┐
    │  Email 3    │         │   Email 2    │
    │   NGAY LẬP  │         │   NGAY LẬP   │
    │   TỨC (✅)  │         │   TỨC (✅)   │
    └─────────────┘         └──────────────┘
           │                       │
           │                       ▼
           │              ┌──────────────┐
           │              │  Lên lịch    │
           │              │  sau 1 ngày  │
           │              │  nữa (3 ngày)│
           │              └──────────────┘
           │                       │
           │                       ▼ (APScheduler)
           │              ┌──────────────┐
           │              │   Email 3    │
           │              │   NGAY LẬP   │
           │              │   TỨC (✅)   │
           │              └──────────────┘
           │                       │
           ▼                       ▼
    ┌──────────────────────────────────────┐
    │   KHI HẾT: 3 EMAILS ĐÃ GỬI ✅      │
    │   Tất cả emails từ: hi@dozenko.io.vn│
    └──────────────────────────────────────┘
```

---

## 📬 Email Templates

```
╔════════════════════════════════════════════════════════════╗
║                   EMAIL 1: WELCOME                         ║
╠════════════════════════════════════════════════════════════╣
║ FROM: hi@dozenko.io.vn                                     ║
║ TO: customer@example.com                                   ║
║ SUBJECT: Chào bạn! Chúng mình nhận được yêu cầu của bạn 🌸 ║
║                                                            ║
║ ✅ Cảm ơn đã quan tâm Dozenko                             ║
║ ✅ Giới thiệu sơ lược sản phẩm                            ║
║ ✅ 3 điểm nổi bật                                         ║
║ ✅ Thông báo email tiếp theo                              ║
╠════════════════════════════════════════════════════════════╣
║ TRIGGER: Ngay lập tức sau khi submit form                  ║
║ DELAY: Không (hoặc vài giây)                              ║
╚════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════╗
║                EMAIL 2: PRODUCT DETAILS                    ║
╠════════════════════════════════════════════════════════════╣
║ FROM: hi@dozenko.io.vn                                     ║
║ TO: customer@example.com                                   ║
║ SUBJECT: Khám phá bộ sưu tập thảm hoa Dozenko 🎨          ║
║                                                            ║
║ ✅ Tại sao chọn Dozenko (100% thủ công, cotton, etc.)     ║
║ ✅ Kích thước & Giá (250k-1M+ tuỳ combo)                  ║
║ ✅ Combo giảm giá                                          ║
║ ✅ Giao hàng toàn quốc                                     ║
║ 🔗 BUTTON: "Xem Bộ Sưu Tập & Đặt Hàng"                    ║
╠════════════════════════════════════════════════════════════╣
║ TRIGGER: Sau 2 ngày (48 giờ)                              ║
║ DELAY: 2 ngày từ form submission                           ║
╚════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════╗
║               EMAIL 3: CALL TO ACTION                      ║
╠════════════════════════════════════════════════════════════╣
║ FROM: hi@dozenko.io.vn                                     ║
║ TO: customer@example.com                                   ║
║ SUBJECT: Đặt hàng thảm Dozenko ngay - Hàng có hạn! ⚡     ║
║                                                            ║
║ ✅ Hàng còn hạn (chỉ 15 tấm)                              ║
║ ✅ 4 lý do đặt hàng ngay                                   ║
║ ✅ Testimonials từ khách hàng                              ║
║ ✅ Urgency messaging                                       ║
║ 🔗 BUTTON: "ĐẶT HÀNG NGAY - HÀNG CÓ HẠN! ⚡" (RED)        ║
║ ℹ️  Zalo: 0123 456 789 (24/7)                              ║
╠════════════════════════════════════════════════════════════╣
║ TRIGGER: Sau 3 ngày (72 giờ)                              ║
║ DELAY: 3 ngày từ form submission                           ║
╚════════════════════════════════════════════════════════════╝
```

---

## 🧪 Test Mode vs Normal Mode

```
┌──────────────────────────────────────────────────────────┐
│                    TEST MODE (+test)                     │
│         Email: customer+test@example.com                 │
├──────────────────────────────────────────────────────────┤
│ Timeline:                                                │
│ Time 0s: Submit form                                     │
│ Time 1s: ✅ Email 1 Sent                                 │
│ Time 2s: ✅ Email 2 Sent                                 │
│ Time 3s: ✅ Email 3 Sent                                 │
├──────────────────────────────────────────────────────────┤
│ Result: Tất cả 3 emails trong hộp thư trong vài giây     │
│ From: hi@dozenko.io.vn ✅                                │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                 NORMAL MODE (Regular)                    │
│        Email: customer@example.com                       │
├──────────────────────────────────────────────────────────┤
│ Timeline:                                                │
│ Day 0 (Time 0s): Submit form                             │
│ Day 0 (Time 1s): ✅ Email 1 Sent                         │
│ Day 0: Database: email1_sent=1, email2_scheduled=Day 2   │
│                                                          │
│ ... (48 hours later) ...                                 │
│ Day 2 (APScheduler): ✅ Email 2 Sent                     │
│ Day 2: Database: email2_sent=1, email3_scheduled=Day 3   │
│                                                          │
│ ... (24 hours later) ...                                 │
│ Day 3 (APScheduler): ✅ Email 3 Sent                     │
│ Day 3: Database: email3_sent=1                           │
├──────────────────────────────────────────────────────────┤
│ Result: Emails spaced out over 3 days                    │
│ From: hi@dozenko.io.vn ✅                                │
└──────────────────────────────────────────────────────────┘
```

---

## 🔄 APScheduler Background Job

```
┌─────────────────────────────────────────────┐
│  Flask App Starts                           │
│  app.run()                                  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  APScheduler Initialized                    │
│  init_scheduler()                           │
│  ✅ Email sequence scheduler started        │
└────────────────┬────────────────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │ Every Minute  │
         │  (recurring)  │
         └───────┬───────┘
                 │
                 ▼
    ┌────────────────────────┐
    │ _process_pending_      │
    │  email_sequences()     │
    └────────────┬───────────┘
                 │
         ┌───────┴───────┐
         │               │
         ▼               ▼
    ┌─────────┐   ┌──────────┐
    │ Email 2 │   │ Email 3  │
    │ Ready?  │   │ Ready?   │
    └────┬────┘   └────┬─────┘
         │             │
    YES  │ NO     YES  │ NO
         │             │
         ▼             ▼
    ┌────────┐   ┌──────────┐
    │ SEND!  │   │ Skip     │
    │  ✅    │   │ Check    │
    │        │   │ next time│
    └────────┘   └──────────┘
         │
         └─────────────────────────┐
                                   │
                              (Loop repeats)
```

---

## 💾 Database Structure

```
DATABASE: brain.db

TABLE: email_sequences
┌─────────────────────────────────────────────────────────┐
│ ID │ customer_id │ customer_email      │ customer_name  │
│ 1  │ 5           │ admin+test@gmail.com│ Test User      │
│ 2  │ 6           │ user1+test@ex.com   │ User One       │
│ 3  │ 7           │ regularuser1@ex.com │ Regular User   │
└─────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ email1_sent │ email1_sent_at       │ email2_sent │ ...   │
│ 1           │ 2026-06-21T09:27:59Z │ 0           │ ...   │
│ 1           │ 2026-06-21T09:30:00Z │ 1           │ ...   │
│ 1           │ 2026-06-21T10:00:00Z │ 0           │ ...   │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ is_test_mode │ created_at           │ Notes              │
│ 1            │ 2026-06-21T09:27:59Z │ Test mode ✅       │
│ 1            │ 2026-06-21T09:30:00Z │ Test mode ✅       │
│ 0            │ 2026-06-21T10:00:00Z │ Normal mode (sched)│
└──────────────────────────────────────────────────────────┘
```

---

## 🌐 API Endpoints Flow

```
Form Submission
      │
      ▼
  POST /api/customers
      │
      ├─────────────────────────┐
      │                         │
      ▼                         ▼
  Extract Email        Check +test?
      │                        │
      └────────────┬───────────┘
                   │
           ┌───────┴────────┐
           │                │
           ▼                ▼
    ┌──────────────┐   ┌─────────────┐
    │ +test Found  │   │ No +test    │
    └──────┬───────┘   └──────┬──────┘
           │                  │
           ▼                  ▼
    Send Email 1-3     Send Email 1
    IMMEDIATELY        Schedule 2&3
           │                  │
           ▼                  ▼
    Database Mark      Database Update
    All Sent (1)       Email1 sent=1
           │                  │
           └────────────┬─────┘
                        │
                        ▼
            Response: Customer Created
            Database Updated
            
GET /api/email-sequences
      │
      ▼
View All Records
(last 50)

GET /api/email-sequences/<id>
      │
      ▼
View Specific Record

POST /api/test-email-sequence
      │
      ▼
Force Send All 3 Emails
(for admin testing)
```

---

## ⏰ Scheduler Timing Example

```
SCENARIO: Customer submits form on June 21, 10:00 AM UTC

Email 1 (Immediate):
├─ Jun 21 10:00:05 AM → ✅ SENT (5 seconds later)

Email 2 (Scheduled for +2 days):
├─ Jun 21 10:00 AM: Schedule set for Jun 23 10:00 AM
├─ Jun 22 10:00 AM: Scheduler checks - not yet (skip)
├─ Jun 23 10:00 AM: Scheduler checks - READY → ✅ SENT
├─ Jun 24 10:00 AM: Scheduler checks - already sent (skip)

Email 3 (Scheduled for +3 days total):
├─ Jun 21 10:00 AM: Schedule set for Jun 24 10:00 AM
├─ Jun 23 10:00 AM: Scheduler checks - not yet (skip)
├─ Jun 24 10:00 AM: Scheduler checks - READY → ✅ SENT
├─ Jun 25 10:00 AM: Scheduler checks - already sent (skip)

RESULT: 3 emails sent automatically over 3 days
        No manual intervention needed!
```

---

## ✅ System Checklist

```
✅ Email 1 - Welcome (Immediate)
✅ Email 2 - Details (Day 2)
✅ Email 3 - CTA (Day 3)
✅ Test Mode (+test modifier)
✅ APScheduler Background Job
✅ Database Table (email_sequences)
✅ API Endpoints (4 new endpoints)
✅ Custom Domain (hi@dozenko.io.vn)
✅ HTML Email Templates
✅ Error Handling
✅ Production Ready

DEPLOYMENT: Ready to move to production! 🚀
```

---

## 🎉 Summary

**Total Implementation Time**: Complete ✅

**Components**:
- 3 Email Templates ✅
- Automatic Scheduling ✅
- Test Mode ✅
- Database Tracking ✅
- Background Scheduler ✅
- API Endpoints ✅
- Documentation ✅

**Status**: PRODUCTION READY 🚀
