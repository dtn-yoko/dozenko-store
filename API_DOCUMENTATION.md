# Email Sequence System - API Documentation

## Overview

The email sequence system automatically sends a series of 3 emails to customers when they submit the form. It supports both immediate delivery (test mode) and scheduled delivery (production mode).

## Endpoints

### 1. Create Customer (Triggers Email Sequence)

**Endpoint**: `POST /api/customers`

**Request Body**:
```json
{
  "name": "Customer Name",
  "phone": "0987654321",
  "email": "customer@example.com",
  "zalo": "0987654321"
}
```

**Response** (201 Created):
```json
{
  "id": 7,
  "name": "Customer Name",
  "phone": "0987654321",
  "email": "customer@example.com",
  "zalo": "0987654321",
  "signup_date": "2026-06-21T10:00:00Z"
}
```

**Auto-Triggered Actions**:
- If email contains `+test`: All 3 emails sent immediately
- If email is normal: Email 1 sent immediately, Emails 2&3 scheduled

---

### 2. List All Email Sequences

**Endpoint**: `GET /api/email-sequences`

**Response** (200 OK):
```json
[
  {
    "id": 3,
    "customer_id": 7,
    "customer_email": "customer@example.com",
    "customer_name": "Customer Name",
    "email1_sent": 1,
    "email1_sent_at": "2026-06-21T10:00:05Z",
    "email2_sent": 0,
    "email2_scheduled_at": "2026-06-23T10:00:00Z",
    "email2_sent_at": null,
    "email3_sent": 0,
    "email3_scheduled_at": "2026-06-24T10:00:00Z",
    "email3_sent_at": null,
    "is_test_mode": 0,
    "created_at": "2026-06-21T10:00:00Z"
  }
]
```

**Query Parameters**: None (returns last 50 sequences)

---

### 3. Get Specific Email Sequence

**Endpoint**: `GET /api/email-sequences/<seq_id>`

**Path Parameters**:
- `seq_id` (integer): Email sequence ID

**Response** (200 OK):
```json
{
  "id": 3,
  "customer_id": 7,
  "customer_email": "customer@example.com",
  "customer_name": "Customer Name",
  "email1_sent": 1,
  "email1_sent_at": "2026-06-21T10:00:05Z",
  "email2_sent": 0,
  "email2_scheduled_at": "2026-06-23T10:00:00Z",
  "email2_sent_at": null,
  "email3_sent": 0,
  "email3_scheduled_at": "2026-06-24T10:00:00Z",
  "email3_sent_at": null,
  "is_test_mode": 0,
  "created_at": "2026-06-21T10:00:00Z"
}
```

**Error Response** (404 Not Found):
```json
{
  "error": "sequence not found"
}
```

---

### 4. Test Email Sequence (Send All 3 Immediately)

**Endpoint**: `POST /api/test-email-sequence`

**Request Body**:
```json
{
  "email": "test@example.com",
  "name": "Test User"
}
```

**Response** (200 OK):
```json
{
  "ok": true,
  "message": "All 3 emails sent immediately (test mode)",
  "customer_id": 8,
  "email": "test@example.com"
}
```

**Error Response** (400 Bad Request):
```json
{
  "error": "email is required"
}
```

**Error Response** (502 Bad Gateway):
```json
{
  "ok": false,
  "error": "Failed to send Email 1: HTTP 401: Unauthorized"
}
```

---

## Email Sequence Logic

### Test Mode (Email contains `+test`)
```
User fills form with email: customer+test@example.com
↓
Email 1 sent immediately ✅
↓
Email 2 sent immediately ✅
↓
Email 3 sent immediately ✅
↓
All 3 emails in inbox within seconds
```

### Normal Mode (Regular email)
```
User fills form with email: customer@example.com
↓
Email 1 sent immediately ✅
↓
APScheduler waits 2 days
↓
Email 2 sent automatically ✅
↓
APScheduler waits 1 more day (3 days total)
↓
Email 3 sent automatically ✅
```

---

## Email Templates

### Email 1: Welcome
- **Subject**: Chào bạn! Chúng mình nhận được yêu cầu của bạn 🌸
- **Content**: Welcome message, product intro
- **Trigger**: Immediately after form submission
- **Send Time**: Instant

### Email 2: Product Details
- **Subject**: Khám phá bộ sưu tập thảm hoa Dozenko 🎨
- **Content**: Detailed product info, pricing, combos
- **CTA Button**: "Xem Bộ Sưu Tập & Đặt Hàng"
- **Trigger**: After 2 days (48 hours)
- **Send Time**: Day 2, same time as form submission

### Email 3: Call to Action
- **Subject**: Đặt hàng thảm Dozenko ngay - Hàng có hạn! ⚡
- **Content**: Urgency, testimonials, limited stock
- **CTA Button**: "ĐẶT HÀNG NGAY - HÀNG CÓ HẠN! ⚡"
- **Trigger**: After 3 days total (1 day after Email 2)
- **Send Time**: Day 3, same time as form submission

---

## Database Schema

### email_sequences Table

```sql
CREATE TABLE email_sequences (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  customer_email TEXT NOT NULL,
  customer_name TEXT NOT NULL,
  sequence_type TEXT DEFAULT 'waitlist',
  
  -- Email 1
  email1_sent BOOLEAN DEFAULT 0,
  email1_sent_at TEXT,
  
  -- Email 2
  email2_sent BOOLEAN DEFAULT 0,
  email2_scheduled_at TEXT,
  email2_sent_at TEXT,
  
  -- Email 3
  email3_sent BOOLEAN DEFAULT 0,
  email3_scheduled_at TEXT,
  email3_sent_at TEXT,
  
  -- Metadata
  is_test_mode BOOLEAN DEFAULT 0,
  created_at TEXT NOT NULL,
  
  FOREIGN KEY(customer_id) REFERENCES customers(id)
);
```

---

## Configuration

### Required Configuration (resend_config.txt)
```
RESEND_API_KEY=re_HWLGTnaA_MBVwsN98ZbXPjjxMYNLUo2kw
FROM_EMAIL=hi@dozenko.io.vn
```

### Optional Configuration (Environment Variables)
```bash
PAYMENT_LINK=https://dozenko.io.vn/thanh-toan
```

---

## Background Scheduler

### APScheduler Configuration
- **Type**: BackgroundScheduler
- **Interval**: Every 1 minute
- **Job**: `_process_pending_email_sequences()`
- **Checks**:
  1. Sequences where `email2_scheduled_at <= now` and `email2_sent == 0`
  2. Sequences where `email3_scheduled_at <= now` and `email3_sent == 0`

### Scheduler Lifecycle
- Started automatically when app.py runs
- Prints: `✅ Email sequence scheduler started`
- Runs continuously in background
- Handles multiple instances with `replace_existing=True`

---

## Error Handling

### Common Errors

**Email sending fails**:
```json
{
  "ok": false,
  "error": "HTTP 401: Unauthorized"
}
```
→ Check RESEND_API_KEY in resend_config.txt

**Missing email in request**:
```json
{
  "error": "email is required"
}
```
→ Provide email in request body

**Invalid resend config**:
```json
{
  "error": "resend_config missing RESEND_API_KEY or FROM_EMAIL"
}
```
→ Verify resend_config.txt file exists and has both keys

---

## Example Usage with curl

### Create Customer (Triggers Email 1)
```bash
curl -X POST http://localhost:5000/api/customers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "phone": "0912345678",
    "email": "john+test@example.com"
  }'
```

### List All Sequences
```bash
curl http://localhost:5000/api/email-sequences
```

### Get Specific Sequence
```bash
curl http://localhost:5000/api/email-sequences/3
```

### Test Email Sequence
```bash
curl -X POST http://localhost:5000/api/test-email-sequence \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "name": "Test User"
  }'
```

---

## Performance Considerations

- **Database Queries**: Optimized with `ORDER BY` and `LIMIT`
- **Scheduler**: Runs every minute (configurable)
- **Email Sending**: Async via Resend API (20 second timeout)
- **Memory**: APScheduler runs in background, minimal overhead

---

## Security Notes

- Resend API key stored in resend_config.txt (not in code)
- Can be overridden with environment variables
- No sensitive data logged to database
- Test mode identified by `+test` pattern (email+addressing)

---

## Support & Testing

For support or to test the system:

1. Use `/api/test-email-sequence` endpoint for immediate testing
2. Check `/api/email-sequences` to view all sequences
3. Look for emails from `hi@dozenko.io.vn` (your custom domain)
4. Check app.py terminal logs for any errors
