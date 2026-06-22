from __future__ import annotations

import sqlite3
import re
import json
import os
import shutil
import base64
import threading
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import hmac
import hashlib
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger


BASE_DIR = Path(__file__).resolve().parent
SEED_DB_PATH = BASE_DIR / "brain.db"
DB_PATH = Path(os.getenv("DB_PATH", str(SEED_DB_PATH)))
RESEND_CONFIG_PATH = BASE_DIR / "resend_config.txt"

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})


def _ensure_db_file() -> None:
    """If DB_PATH points to a persistent disk that's still empty (first boot),
    seed it from the repo's bundled brain.db so products/brand-voice survive."""
    if DB_PATH == SEED_DB_PATH:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists() and SEED_DB_PATH.exists():
        shutil.copy(SEED_DB_PATH, DB_PATH)


# --- GitHub-as-storage backup: free workaround for Render's ephemeral disk on
# the free plan. Pulls the latest brain.db backup on boot, pushes a fresh
# backup on an interval while running. No-ops if GITHUB_TOKEN isn't set.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "dtn-yoko/dozenko-store").strip()
GITHUB_BACKUP_BRANCH = os.getenv("GITHUB_BACKUP_BRANCH", "db-backup").strip()
GITHUB_BACKUP_PATH = os.getenv("GITHUB_BACKUP_PATH", "brain.db").strip()


def _github_api_url() -> str:
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_BACKUP_PATH}"


def _github_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "DozenkoCRM/1.0",
    }


def restore_db_from_github() -> None:
    """Download the latest brain.db backup from GITHUB_BACKUP_BRANCH on boot."""
    if not GITHUB_TOKEN:
        return
    try:
        resp = requests.get(
            _github_api_url(),
            headers=_github_headers(),
            params={"ref": GITHUB_BACKUP_BRANCH},
            timeout=20,
        )
        if not resp.ok:
            print(f"[db-backup] restore skipped: HTTP {resp.status_code}")
            return
        content_b64 = resp.json().get("content", "")
        if not content_b64:
            return
        data = base64.b64decode(content_b64)
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        DB_PATH.write_bytes(data)
        print("[db-backup] restored brain.db from GitHub backup")
    except Exception as exc:
        print(f"[db-backup] restore failed: {exc}")


def backup_db_to_github_async() -> None:
    """Fire-and-forget backup so request handlers don't wait on GitHub's API."""
    if not GITHUB_TOKEN:
        return
    threading.Thread(target=backup_db_to_github, daemon=True).start()


def _snapshot_db_bytes() -> bytes:
    """Use SQLite's online backup API for a consistent snapshot instead of
    reading the raw file, which can race with concurrent writers (esp. WAL)."""
    snapshot_path = DB_PATH.with_suffix(".snapshot.db")
    src = sqlite3.connect(DB_PATH, timeout=30)
    try:
        dst = sqlite3.connect(snapshot_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
        return snapshot_path.read_bytes()
    finally:
        src.close()
        snapshot_path.unlink(missing_ok=True)


def backup_db_to_github() -> None:
    """Push the current brain.db to GITHUB_BACKUP_BRANCH so it survives restarts."""
    if not GITHUB_TOKEN or not DB_PATH.exists():
        return
    try:
        get_resp = requests.get(
            _github_api_url(),
            headers=_github_headers(),
            params={"ref": GITHUB_BACKUP_BRANCH},
            timeout=20,
        )
        sha = get_resp.json().get("sha") if get_resp.ok else None

        content_b64 = base64.b64encode(_snapshot_db_bytes()).decode("ascii")
        payload = {
            "message": f"chore: auto-backup brain.db {now_iso()}",
            "content": content_b64,
            "branch": GITHUB_BACKUP_BRANCH,
        }
        if sha:
            payload["sha"] = sha

        put_resp = requests.put(
            _github_api_url(),
            headers=_github_headers(),
            json=payload,
            timeout=20,
        )
        if not put_resp.ok:
            print(f"[db-backup] push failed: HTTP {put_resp.status_code}: {put_resp.text}")
    except Exception as exc:
        print(f"[db-backup] push failed: {exc}")


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def is_valid_vn_phone(phone: str) -> bool:
    # Accept local VN style: 10-11 digits.
    return bool(re.fullmatch(r"\d{10,11}", phone or ""))


def is_valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email or ""))


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 30000")
    return con


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def _load_resend_config() -> dict[str, str]:
    config: dict[str, str] = {
        "RESEND_API_KEY": os.getenv("RESEND_API_KEY", "").strip(),
        "FROM_EMAIL": os.getenv("FROM_EMAIL", "").strip(),
    }

    # If both env vars are present, no need to read local file.
    if config["RESEND_API_KEY"] and config["FROM_EMAIL"]:
        return config

    if not RESEND_CONFIG_PATH.exists():
        return config

    for raw_line in RESEND_CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed_key = key.strip()
        parsed_value = value.strip()
        if parsed_key and parsed_value and not config.get(parsed_key):
            config[parsed_key] = parsed_value
    return config


def _send_resend_email(to_email: str, subject: str, html: str) -> tuple[bool, str]:
    config = _load_resend_config()
    api_key = config.get("RESEND_API_KEY", "")
    from_email = config.get("FROM_EMAIL", "")

    if not api_key or not from_email:
        return False, "resend_config missing RESEND_API_KEY or FROM_EMAIL"

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": html,
    }

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "DozenkoCRM/1.0",
            },
            json=payload,
            timeout=20,
        )

        if not resp.ok:
            return False, f"HTTP {resp.status_code}: {resp.text}"

        parsed = resp.json() if resp.text else {}
        return True, str(parsed.get("id", "sent"))
    except Exception as exc:
        return False, str(exc)


def _send_welcome_email(customer_name: str, to_email: str) -> tuple[bool, str]:
    safe_name = customer_name.strip() or "ban"
    subject = "Dozenko da nhan thong tin cua ban"
    html = (
        f"<h3>Chao {safe_name},</h3>"
        "<p>Dozenko da nhan thong tin cua ban thanh cong.</p>"
        "<p>Cam on ban da dang ky. Chung minh se gui cap nhat som nhat qua email nay.</p>"
        "<p>Than men,<br>Dozenko</p>"
    )
    return _send_resend_email(to_email=to_email, subject=subject, html=html)


def _send_order_confirmation_email(customer_name: str, to_email: str, product_name: str, amount: float) -> tuple[bool, str]:
    """Send order confirmation email when a new order is created."""
    if not to_email:
        return False, "missing customer email"
    safe_name = customer_name.strip() or "bạn"
    amount_str = f"{amount:,.0f}".replace(",", ".")
    subject = f"Dozenko đã nhận đơn hàng của bạn - {product_name} 🌸"
    html = (
        f"<h2>Chào {safe_name}!</h2>"
        f"<p>Cảm ơn bạn đã đặt hàng tại <strong>Dozenko</strong>. Đơn hàng của bạn đã được ghi nhận:</p>"
        f"<ul>"
        f"<li><strong>Sản phẩm:</strong> {product_name}</li>"
        f"<li><strong>Số tiền:</strong> {amount_str}đ</li>"
        f"</ul>"
        f"<p>Sau khi xác nhận thanh toán, đội ngũ Dozenko sẽ đóng gói và gửi thảm đến bạn trong thời gian sớm nhất. "
        f"Chúng mình sẽ liên hệ qua điện thoại/Zalo để xác nhận địa chỉ nhận hàng.</p>"
        f"<p>Nếu có bất kỳ câu hỏi nào, hãy liên hệ ngay với chúng mình.</p>"
        f"<p>🌸 Thân mến,<br><strong>Đội Dozenko</strong></p>"
    )
    return _send_resend_email(to_email=to_email, subject=subject, html=html)


def _get_payment_link() -> str:
    """Get the payment/checkout link from config or environment"""
    return os.getenv("PAYMENT_LINK", "https://dozenko.io.vn/thanh-toan").strip()


def _is_test_email(email: str) -> bool:
    """Check if email is in test mode (contains +test)"""
    return "+test" in (email or "").lower()


def _create_email_sequence(customer_id: int, customer_email: str, customer_name: str, is_test: bool) -> int:
    """Create an email sequence record in the database"""
    with closing(get_connection()) as con:
        cur = con.cursor()
        now = now_iso()
        
        # Schedule times for non-test mode
        email2_scheduled = (datetime.utcnow() + timedelta(days=2)).replace(microsecond=0).isoformat() + "Z" if not is_test else now
        email3_scheduled = (datetime.utcnow() + timedelta(days=3)).replace(microsecond=0).isoformat() + "Z" if not is_test else now
        
        cur.execute(
            """
            INSERT INTO email_sequences(
                customer_id, customer_email, customer_name, sequence_type,
                email2_scheduled_at, email3_scheduled_at, is_test_mode, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (customer_id, customer_email, customer_name, "waitlist", email2_scheduled, email3_scheduled, is_test, now)
        )
        con.commit()
        return cur.lastrowid


def _send_email1_and_schedule(customer_id: int, customer_email: str, customer_name: str, is_test: bool) -> tuple[bool, str]:
    """Send Email 1 immediately and create sequence record"""
    # Send Email 1
    ok, msg = _send_email1_welcome(customer_name, customer_email)
    if not ok:
        return False, f"Failed to send Email 1: {msg}"
    
    # Create sequence record
    seq_id = _create_email_sequence(customer_id, customer_email, customer_name, is_test)
    
    # Mark Email 1 as sent
    with closing(get_connection()) as con:
        cur = con.cursor()
        cur.execute(
            """
            UPDATE email_sequences
            SET email1_sent = 1, email1_sent_at = ?
            WHERE id = ?
            """,
            (now_iso(), seq_id)
        )
        con.commit()
    
    return True, f"Email 1 sent, sequence created (ID: {seq_id})"


def _process_pending_email_sequences() -> None:
    """Background job to send scheduled emails"""
    with closing(get_connection()) as con:
        cur = con.cursor()
        now = now_iso()
        
        # Email 2: Check sequences where email2 should be sent
        pending_email2 = cur.execute(
            """
            SELECT id, customer_email, customer_name, email2_scheduled_at
            FROM email_sequences
            WHERE email2_sent = 0 AND email1_sent = 1 AND email2_scheduled_at <= ?
            ORDER BY id ASC
            """,
            (now,)
        ).fetchall()
        
        for row in pending_email2:
            seq_id = row["id"]
            email = row["customer_email"]
            name = row["customer_name"]
            
            ok, msg = _send_email2_details(name, email)
            if ok:
                cur.execute(
                    """
                    UPDATE email_sequences
                    SET email2_sent = 1, email2_sent_at = ?
                    WHERE id = ?
                    """,
                    (now_iso(), seq_id)
                )
        
        # Email 3: Check sequences where email3 should be sent
        pending_email3 = cur.execute(
            """
            SELECT id, customer_email, customer_name, email3_scheduled_at
            FROM email_sequences
            WHERE email3_sent = 0 AND email2_sent = 1 AND email3_scheduled_at <= ?
            ORDER BY id ASC
            """,
            (now,)
        ).fetchall()
        
        for row in pending_email3:
            seq_id = row["id"]
            email = row["customer_email"]
            name = row["customer_name"]
            
            ok, msg = _send_email3_cta(name, email)
            if ok:
                cur.execute(
                    """
                    UPDATE email_sequences
                    SET email3_sent = 1, email3_sent_at = ?
                    WHERE id = ?
                    """,
                    (now_iso(), seq_id)
                )
        
        con.commit()


def _send_all_emails_immediately(customer_id: int, customer_email: str, customer_name: str) -> tuple[bool, str]:
    """Send all 3 emails immediately (test mode) with delay to avoid Resend rate limit (2 req/s)."""
    import time as _time

    # Create sequence record first so we can track partial success
    seq_id = _create_email_sequence(customer_id, customer_email, customer_name, True)

    errors = []

    # Email 1
    ok1, msg1 = _send_email1_welcome(customer_name, customer_email)
    if ok1:
        with closing(get_connection()) as con:
            con.execute(
                "UPDATE email_sequences SET email1_sent=1, email1_sent_at=? WHERE id=?",
                (now_iso(), seq_id),
            )
            con.commit()
    else:
        errors.append(f"Email 1 failed: {msg1}")

    _time.sleep(0.6)  # Stay under 2 req/s Resend limit

    # Email 2
    ok2, msg2 = _send_email2_details(customer_name, customer_email)
    if ok2:
        with closing(get_connection()) as con:
            con.execute(
                "UPDATE email_sequences SET email2_sent=1, email2_sent_at=? WHERE id=?",
                (now_iso(), seq_id),
            )
            con.commit()
    else:
        errors.append(f"Email 2 failed: {msg2}")

    _time.sleep(0.6)

    # Email 3
    ok3, msg3 = _send_email3_cta(customer_name, customer_email)
    if ok3:
        with closing(get_connection()) as con:
            con.execute(
                "UPDATE email_sequences SET email3_sent=1, email3_sent_at=? WHERE id=?",
                (now_iso(), seq_id),
            )
            con.commit()
    else:
        errors.append(f"Email 3 failed: {msg3}")

    if errors:
        return False, " | ".join(errors)

    return True, "All 3 emails sent immediately (test mode)"


def _send_email1_welcome(customer_name: str, to_email: str) -> tuple[bool, str]:
    """Email 1: Welcome email (sent immediately)"""
    safe_name = customer_name.strip() or "bạn"
    subject = "Chào bạn! Chúng mình nhận được yêu cầu của bạn 🌸"
    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>Chào {safe_name}!</h2>
        
        <p>Cảm ơn bạn đã quan tâm đến <strong>Thảm Hoa Dozenko</strong>!</p>
        
        <p>Chúng mình đã nhận được đơn đăng ký của bạn. Những tấm thảm thủ công này được chần tay từ cotton cao cấp, mềm mại và có họa tiết hoa độc đáo.</p>
        
        <p><strong>🎁 Chương Trình Đặc Biệt:</strong></p>
        <ul>
            <li>✨ Thảm 50cm × 120cm từ 300,000đ</li>
            <li>🚚 Mua 2+ tặng miễn phí vận chuyển</li>
            <li>🌸 4 màu sắc khác nhau có sẵn</li>
        </ul>
        
        <p>Đội ngũ Dozenko sẽ gửi thêm thông tin chi tiết trong email tiếp theo. Hãy chú ý hộp thư của bạn!</p>
        
        <p>Nếu có bất kỳ câu hỏi nào, hãy liên hệ ngay với chúng mình.</p>
        
        <p>🌸 Thân mến,<br>
        <strong>Đội Dozenko</strong></p>
    </div>
    """
    return _send_resend_email(to_email=to_email, subject=subject, html=html)


def _send_email2_details(customer_name: str, to_email: str) -> tuple[bool, str]:
    """Email 2: Product details (sent after 2 days)"""
    safe_name = customer_name.strip() or "bạn"
    payment_link = _get_payment_link()
    subject = "Khám phá bộ sưu tập thảm hoa Dozenko 🎨"
    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>Bộ Sưu Tập Dozenko - Nghệ Thuật Dưới Chân Bạn</h2>
        
        <p>Xin chào {safe_name},</p>
        
        <p>Sau khi bạn đăng ký, chúng mình muốn giới thiệu thêm về quy trình tạo ra mỗi tấm thảm của Dozenko.</p>
        
        <p><strong>🌸 Tại Sao Chọn Dozenko?</strong></p>
        <ul>
            <li><strong>100% Thủ Công:</strong> Mỗi tấm thảm được chần tay bởi các nghệ nhân</li>
            <li><strong>Cotton Cao Cấp:</strong> Mềm mại, bền lâu, an toàn cho gia đình</li>
            <li><strong>Họa Tiết Độc Đáo:</strong> Những mẫu hoa tươi sáng, mới lạ</li>
            <li><strong>Đế Chống Trượt:</strong> Bảo vệ sàn nhà và an toàn cho trẻ em</li>
        </ul>
        
        <p><strong>📏 Kích Thước & Giá:</strong></p>
        <ul>
            <li>50cm × 120cm: 300,000đ</li>
            <li>Mua 2 tấm: 550,000đ (tiết kiệm 50,000đ)</li>
            <li>Mua 3 tấm: 750,000đ (tiết kiệm 150,000đ)</li>
            <li>Mua 4 tấm: 900,000đ (tiết kiệm 300,000đ)</li>
        </ul>
        
        <p><strong>🎯 Giao Hàng Toàn Quốc</strong></p>
        <p>Miễn phí vận chuyển khi mua 2+ tấm. Chúng mình giao trong 2-3 ngày làm việc.</p>
        
        <p>Chuẩn bị sẵn sàng để thay đổi không gian của bạn? 👇</p>
        
        <p style="text-align: center; margin-top: 30px;">
            <a href="{payment_link}" style="background-color: #d4af5f; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block; font-weight: bold;">
                ➤ Xem Bộ Sưu Tập & Đặt Hàng
            </a>
        </p>
        
        <p>🌸 Thân mến,<br>
        <strong>Đội Dozenko</strong></p>
    </div>
    """
    return _send_resend_email(to_email=to_email, subject=subject, html=html)


def _send_email3_cta(customer_name: str, to_email: str) -> tuple[bool, str]:
    """Email 3: Call to action (sent after 3 days total, 1 day after email 2)"""
    safe_name = customer_name.strip() or "bạn"
    payment_link = _get_payment_link()
    subject = "Đặt hàng thảm Dozenko ngay - Hàng có hạn! ⚡"
    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>Hàng Còn Hạn - Đừng Bỏ Lỡ Cơ Hội! ⚡</h2>
        
        <p>Xin chào {safe_name},</p>
        
        <p>Bộ sưu tập Dozenko được yêu thích rất nhiều, và số lượng còn lại không nhiều.</p>
        
        <p><strong>🔥 Tại Sao Bạn Nên Đặt Hàng Ngay?</strong></p>
        <ul>
            <li>✅ Hàng còn hạn (chỉ 15 tấm với giá này)</li>
            <li>✅ Mua 2+ tặng miễn phí vận chuyển</li>
            <li>✅ Giao hàng nhanh (2-3 ngày làm việc)</li>
            <li>✅ 100% thủ công, chất lượng đảm bảo</li>
        </ul>
        
        <p><strong>😍 Khách Hàng Yêu Thích:</strong></p>
        <p><em>"Thảm rất đẹp, mềm và bền. Toàn nhà tôi đều thích!"</em> - Chị Hà, Hà Nội</p>
        <p><em>"Giao hàng nhanh, sản phẩm đúng như hình. Rất hài lòng!"</em> - Anh Minh, TP.HCM</p>
        
        <p><strong>⏰ Thời Gian Hạn Chế:</strong></p>
        <p>Số lượng với giá khuyến mãi này sẽ hết rất nhanh. Bạn nên đặt hôm nay để không bỏ lỡ cơ hội!</p>
        
        <p style="text-align: center; margin-top: 30px;">
            <a href="{payment_link}" style="background-color: #ff6b6b; color: white; padding: 14px 28px; font-size: 16px; font-weight: bold; text-decoration: none; border-radius: 4px; display: inline-block;">
                ➤ ĐẶT HÀNG NGAY - HÀNG CÓ HẠN! ⚡
            </a>
        </p>
        
        <p style="margin-top: 20px; color: #666; font-size: 14px;">
            Hoặc liên hệ với chúng mình qua Zalo: 0123 456 789 (hỗ trợ 24/7)
        </p>
        
        <p>🌸 Thân mến,<br>
        <strong>Đội Dozenko</strong></p>
    </div>
    """
    return _send_resend_email(to_email=to_email, subject=subject, html=html)


def _extract_order_id_from_payload(data: dict[str, Any]) -> int | None:
    candidate_texts = [
        data.get("referenceCode"),
        data.get("reference_code"),
        data.get("description"),
        data.get("content"),
        data.get("transferContent"),
        data.get("transfer_content"),
        data.get("memo"),
        data.get("note"),
        data.get("remark"),
        data.get("order_id"),
        data.get("orderId"),
    ]

    for value in candidate_texts:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue

        direct_match = re.search(r"(?:order[_\s-]?id|ORD)\s*[:#-]?\s*(\d+)", text, flags=re.IGNORECASE)
        if direct_match:
            return int(direct_match.group(1))

        if text.isdigit():
            return int(text)

    return None


def _parse_amount(raw: Any) -> float | None:
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip()
    if not text:
        return None

    # Keep digits and separators only, remove currency symbols and spaces.
    text = re.sub(r"[^0-9,\.]", "", text)
    if not text:
        return None

    # 2,000,000.50 -> remove thousand commas
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", text):
        return float(text.replace(",", ""))

    # 2.000.000,50 -> remove thousand dots and normalize decimal comma
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", text):
        return float(text.replace(".", "").replace(",", "."))

    # Plain integer or decimal with dot/comma.
    if re.fullmatch(r"\d+", text):
        return float(text)
    if re.fullmatch(r"\d+[\.,]\d+", text):
        return float(text.replace(",", "."))

    return None


def _extract_amount_from_payload(data: dict[str, Any]) -> float | None:
    amount_keys = [
        "amount",
        "transferAmount",
        "transfer_amount",
        "transactionAmount",
        "transaction_amount",
        "creditAmount",
        "credit_amount",
    ]

    for key in amount_keys:
        raw = data.get(key)
        parsed = _parse_amount(raw)
        if parsed is not None:
            return parsed

    return None


def _extract_payload_candidates(data: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = [data]

    nested_data = data.get("data")
    if isinstance(nested_data, dict):
        candidates.append(nested_data)
    elif isinstance(nested_data, list):
        for item in nested_data:
            if isinstance(item, dict):
                candidates.append(item)

    for key in ("transactions", "items", "records", "history"):
        nested_list = data.get(key)
        if isinstance(nested_list, list):
            for item in nested_list:
                if isinstance(item, dict):
                    candidates.append(item)

    # Deduplicate by object id while preserving order.
    uniq: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in candidates:
        item_id = id(item)
        if item_id in seen:
            continue
        seen.add(item_id)
        uniq.append(item)

    return uniq


def _log_webhook_event(status: str, payload: dict[str, Any], message: str) -> None:
    with closing(get_connection()) as con:
        con.execute(
            """
            INSERT INTO webhook_events(provider, status, payload, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("sepay", status, json.dumps(payload, ensure_ascii=False), message, now_iso()),
        )
        con.commit()


def _process_webhook_payload(data: dict[str, Any]) -> tuple[int | None, str | None]:
    candidates = _extract_payload_candidates(data)

    # Prefer explicit order code match before amount fallback.
    for candidate in candidates:
        order_id = _extract_order_id_from_payload(candidate)
        if order_id is not None:
            return order_id, "order_code"

    for candidate in candidates:
        amount = _extract_amount_from_payload(candidate)
        if amount is None:
            continue
        order_id = _find_pending_order_by_amount(amount)
        if order_id is not None:
            return order_id, "amount"

    return None, None


def _find_pending_order_by_amount(amount: float) -> int | None:
    with closing(get_connection()) as con:
        rows = con.execute(
            """
            SELECT id
            FROM orders
            WHERE status = 'pending' AND ABS(amount - ?) < 0.5
            ORDER BY id DESC
            LIMIT 1
            """,
            (amount,),
        ).fetchall()

    if not rows:
        return None
    return int(rows[0]["id"])


def init_db() -> None:
    with closing(get_connection()) as con:
        cur = con.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('physical', 'digital', 'service')),
                price REAL NOT NULL,
                description TEXT,
                quantity INTEGER,
                created_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                email TEXT,
                zalo TEXT,
                signup_date TEXT NOT NULL
            )
            """
        )

        # Add email column to existing databases that were created without it
        try:
            cur.execute("ALTER TABLE customers ADD COLUMN email TEXT")
        except Exception:
            pass  # Column already exists

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                order_date TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS webhook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS email_sequences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                customer_email TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                sequence_type TEXT DEFAULT 'waitlist',
                email1_sent BOOLEAN DEFAULT 0,
                email1_sent_at TEXT,
                email2_sent BOOLEAN DEFAULT 0,
                email2_scheduled_at TEXT,
                email2_sent_at TEXT,
                email3_sent BOOLEAN DEFAULT 0,
                email3_scheduled_at TEXT,
                email3_sent_at TEXT,
                is_test_mode BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            )
            """
        )

        con.commit()


@app.route("/")
def root():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/admin")
def admin_page():
    return send_from_directory(BASE_DIR, "admin.html")


@app.route("/pay")
@app.route("/thanh-toan")
def pay_page_alias():
    return send_from_directory(BASE_DIR, "pay.html")


@app.route("/pay.html")
def pay_page():
    return send_from_directory(BASE_DIR, "pay.html")


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "time": now_iso()})


@app.route("/api/products", methods=["GET"])
def list_products():
    with closing(get_connection()) as con:
        rows = con.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/products", methods=["POST"])
def create_product():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    ptype = (data.get("type") or "physical").strip().lower()
    description = (data.get("description") or "").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400
    if ptype not in {"physical", "digital", "service"}:
        return jsonify({"error": "invalid product type"}), 400

    try:
        price = float(data.get("price"))
    except (TypeError, ValueError):
        return jsonify({"error": "price must be a number"}), 400

    quantity = data.get("quantity")
    if ptype == "physical":
        if quantity in (None, ""):
            return jsonify({"error": "quantity is required for physical products"}), 400
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return jsonify({"error": "quantity must be an integer"}), 400
    else:
        quantity = None

    with closing(get_connection()) as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO products(name, type, price, description, quantity, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, ptype, price, description, quantity, now_iso()),
        )
        product_id = cur.lastrowid
        con.commit()
        row = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.route("/api/products/<int:product_id>", methods=["PUT"])
def update_product(product_id: int):
    data = request.get_json(silent=True) or {}

    with closing(get_connection()) as con:
        cur = con.cursor()
        existing = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not existing:
            return jsonify({"error": "product not found"}), 404

        name = (data.get("name", existing["name"]) or "").strip()
        ptype = (data.get("type", existing["type"]) or "").strip().lower()
        description = (data.get("description", existing["description"]) or "").strip()

        try:
            price = float(data.get("price", existing["price"]))
        except (TypeError, ValueError):
            return jsonify({"error": "price must be a number"}), 400

        quantity_val = data.get("quantity", existing["quantity"])
        if ptype == "physical":
            if quantity_val in (None, ""):
                return jsonify({"error": "quantity is required for physical products"}), 400
            try:
                quantity_val = int(quantity_val)
            except (TypeError, ValueError):
                return jsonify({"error": "quantity must be an integer"}), 400
        else:
            quantity_val = None

        if ptype not in {"physical", "digital", "service"}:
            return jsonify({"error": "invalid product type"}), 400

        cur.execute(
            """
            UPDATE products
            SET name = ?, type = ?, price = ?, description = ?, quantity = ?
            WHERE id = ?
            """,
            (name, ptype, price, description, quantity_val, product_id),
        )
        con.commit()
        row = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    return jsonify(row_to_dict(row))


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id: int):
    with closing(get_connection()) as con:
        cur = con.cursor()
        in_use = cur.execute("SELECT 1 FROM orders WHERE product_id = ? LIMIT 1", (product_id,)).fetchone()
        if in_use:
            return jsonify({"error": "cannot delete product with existing orders"}), 409
        cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
        con.commit()
    return jsonify({"ok": True})


@app.route("/api/customers", methods=["GET"])
def list_customers():
    with closing(get_connection()) as con:
        rows = con.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/customers", methods=["POST"])
def create_customer():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    phone = normalize_phone((data.get("phone") or "").strip())
    email = (data.get("email") or "").strip() or None
    zalo = (data.get("zalo") or phone).strip()

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not phone:
        return jsonify({"error": "phone is required"}), 400
    if not is_valid_vn_phone(phone):
        return jsonify({"error": "phone must be 10-11 digits"}), 400
    if email and not is_valid_email(email):
        return jsonify({"error": "email is not a valid email address"}), 400

    with closing(get_connection()) as con:
        cur = con.cursor()
        existing = cur.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
        if existing:
            # Update email if provided and existing customer doesn't have one
            if email and not existing["email"]:
                cur.execute("UPDATE customers SET email = ? WHERE id = ?", (email, existing["id"]))
                con.commit()
                row = cur.execute("SELECT * FROM customers WHERE id = ?", (existing["id"],)).fetchone()
                return jsonify(row_to_dict(row)), 200
            return jsonify(row_to_dict(existing)), 200

        cur.execute(
            """
            INSERT INTO customers(name, phone, email, zalo, signup_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, phone, email, zalo, now_iso()),
        )
        customer_id = cur.lastrowid
        con.commit()
        row = cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()

    # Send email sequence after successful new customer creation
    if email:
        is_test = _is_test_email(email)
        if is_test:
            # Test mode: send all 3 emails immediately
            ok, seq_msg = _send_all_emails_immediately(customer_id, email, name)
        else:
            # Normal mode: send Email 1 and schedule Emails 2 and 3
            ok, seq_msg = _send_email1_and_schedule(customer_id, email, name, False)
        
        # Log the sequence info (optional - can be used for debugging)
        if not ok:
            print(f"⚠️  Email sequence error for {email}: {seq_msg}")

    backup_db_to_github_async()
    return jsonify(row_to_dict(row)), 201


@app.route("/api/customers/<int:customer_id>", methods=["PUT"])
def update_customer(customer_id: int):
    data = request.get_json(silent=True) or {}

    with closing(get_connection()) as con:
        cur = con.cursor()
        existing = cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not existing:
            return jsonify({"error": "customer not found"}), 404

        name = (data.get("name", existing["name"]) or "").strip()
        phone = normalize_phone((data.get("phone", existing["phone"]) or "").strip())
        email_val = data.get("email", existing["email"])
        email = (email_val or "").strip() or None
        zalo = (data.get("zalo", existing["zalo"]) or "").strip()

        if not name or not phone:
            return jsonify({"error": "name and phone are required"}), 400
        if not is_valid_vn_phone(phone):
            return jsonify({"error": "phone must be 10-11 digits"}), 400
        if email and not is_valid_email(email):
            return jsonify({"error": "email is not a valid email address"}), 400

        duplicate = cur.execute(
            "SELECT id FROM customers WHERE phone = ? AND id != ?", (phone, customer_id)
        ).fetchone()
        if duplicate:
            return jsonify({"error": "phone already exists"}), 409

        cur.execute(
            "UPDATE customers SET name = ?, phone = ?, email = ?, zalo = ? WHERE id = ?",
            (name, phone, email, zalo, customer_id),
        )
        con.commit()
        row = cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.route("/api/customers/<int:customer_id>", methods=["DELETE"])
def delete_customer(customer_id: int):
    with closing(get_connection()) as con:
        cur = con.cursor()
        in_use = cur.execute("SELECT 1 FROM orders WHERE customer_id = ? LIMIT 1", (customer_id,)).fetchone()
        if in_use:
            return jsonify({"error": "cannot delete customer with existing orders"}), 409
        cur.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        con.commit()
    return jsonify({"ok": True})


def _apply_stock_on_create_order(cur: sqlite3.Cursor, product_id: int, quantity: int) -> tuple[bool, str | None]:
    product = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        return False, "product not found"

    if product["type"] == "physical" and product["quantity"] is not None:
        remain = int(product["quantity"])
        if remain < quantity:
            return False, "not enough stock"
        cur.execute(
            "UPDATE products SET quantity = ? WHERE id = ?",
            (remain - quantity, product_id),
        )
    return True, None


@app.route("/api/orders", methods=["GET"])
def list_orders():
    sql = """
    SELECT
      o.id,
      o.customer_id,
      o.product_id,
      o.amount,
      o.status,
      o.order_date,
      c.name AS customer_name,
      c.phone AS customer_phone,
      p.name AS product_name,
      p.type AS product_type
    FROM orders o
    JOIN customers c ON c.id = o.customer_id
    JOIN products p ON p.id = o.product_id
    ORDER BY o.id DESC
    """
    with closing(get_connection()) as con:
        rows = con.execute(sql).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    try:
        customer_id = int(data.get("customer_id"))
        product_id = int(data.get("product_id"))
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "customer_id, product_id and amount are required"}), 400

    status = (data.get("status") or "pending").strip().lower()
    if status not in {"pending", "success", "failed", "cancelled"}:
        return jsonify({"error": "invalid status"}), 400

    try:
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    if quantity < 1:
        quantity = 1

    with closing(get_connection()) as con:
        cur = con.cursor()

        customer = cur.execute("SELECT id FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not customer:
            return jsonify({"error": "customer not found"}), 404

        ok, err = _apply_stock_on_create_order(cur, product_id, quantity)
        if not ok:
            return jsonify({"error": err}), 400

        cur.execute(
            """
            INSERT INTO orders(customer_id, product_id, amount, status, order_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (customer_id, product_id, amount, status, now_iso()),
        )
        order_id = cur.lastrowid
        con.commit()

    with closing(get_connection()) as con:
        row = con.execute(
            """
            SELECT
              o.id,
              o.customer_id,
              o.product_id,
              o.amount,
              o.status,
              o.order_date,
              c.name AS customer_name,
              c.phone AS customer_phone,
              c.email AS customer_email,
              p.name AS product_name,
              p.type AS product_type
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            JOIN products p ON p.id = o.product_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()

    if row["customer_email"]:
        _send_order_confirmation_email(
            customer_name=row["customer_name"],
            to_email=row["customer_email"],
            product_name=row["product_name"],
            amount=row["amount"],
        )

    backup_db_to_github_async()
    return jsonify(row_to_dict(row)), 201


@app.route("/api/orders/<int:order_id>", methods=["GET"])
def get_order(order_id: int):
    with closing(get_connection()) as con:
        row = con.execute(
            """
            SELECT
              o.id,
              o.customer_id,
              o.product_id,
              o.amount,
              o.status,
              o.order_date,
              c.name AS customer_name,
              c.phone AS customer_phone,
              p.name AS product_name,
              p.type AS product_type
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            JOIN products p ON p.id = o.product_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()
    if not row:
        return jsonify({"error": "order not found"}), 404
    return jsonify(row_to_dict(row))


@app.route("/api/orders/<int:order_id>", methods=["PUT"])
def update_order(order_id: int):
    data = request.get_json(silent=True) or {}

    with closing(get_connection()) as con:
        cur = con.cursor()
        existing = cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not existing:
            return jsonify({"error": "order not found"}), 404

        status = (data.get("status", existing["status"]) or "").strip().lower()
        if status not in {"pending", "success", "failed", "cancelled"}:
            return jsonify({"error": "invalid status"}), 400

        try:
            amount = float(data.get("amount", existing["amount"]))
        except (TypeError, ValueError):
            return jsonify({"error": "amount must be a number"}), 400

        cur.execute(
            "UPDATE orders SET amount = ?, status = ? WHERE id = ?",
            (amount, status, order_id),
        )
        con.commit()

    with closing(get_connection()) as con:
        row = con.execute(
            """
            SELECT
              o.id,
              o.customer_id,
              o.product_id,
              o.amount,
              o.status,
              o.order_date,
              c.name AS customer_name,
              c.phone AS customer_phone,
              p.name AS product_name,
              p.type AS product_type
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            JOIN products p ON p.id = o.product_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()
    return jsonify(row_to_dict(row))


@app.route("/api/orders/<int:order_id>", methods=["DELETE"])
def delete_order(order_id: int):
    with closing(get_connection()) as con:
        con.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        con.commit()
    return jsonify({"ok": True})


def webhook_sepay_helper(data):
    """Helper to process SePay webhook - updates order status"""
    order_id, matched_by = _process_webhook_payload(data)
    if order_id is None or matched_by is None:
        _log_webhook_event("ignored", data, "could not find order id or amount match")
        return jsonify({"error": "could not find order id or amount in webhook payload"}), 400
    
    with closing(get_connection()) as con:
        cur = con.cursor()
        existing = cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not existing:
            _log_webhook_event("ignored", data, f"order not found: {order_id}")
            return jsonify({"error": "order not found"}), 404

        cur.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            ("success", order_id),
        )
        con.commit()

    _log_webhook_event("processed", data, f"order {order_id} marked success by {matched_by}")
    backup_db_to_github_async()
    return jsonify({"ok": True, "order_id": order_id, "matched_by": matched_by}), 200


@app.route("/api/webhook/sepay", methods=["POST"])
def webhook_sepay():
    """
    SePay webhook handler - updates order status on payment confirmation
    Expects: {"referenceCode": "order_id:123", ...}
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({"error": "invalid json"}), 400

    if isinstance(data.get("data"), dict):
        merged = dict(data)
        merged.update(data["data"])
        data = merged
    
    return webhook_sepay_helper(data)


@app.route("/api/webhook/sepay/test/<int:order_id>", methods=["POST"])
def webhook_sepay_test(order_id: int):
    """Test endpoint - simulates SePay webhook for testing"""
    data = {"referenceCode": f"ORD{order_id}", "description": f"ORD{order_id}"}
    return webhook_sepay_helper(data)


@app.route("/api/webhook/events", methods=["GET"])
def webhook_events():
    with closing(get_connection()) as con:
        rows = con.execute(
            """
            SELECT id, provider, status, message, created_at
            FROM webhook_events
            ORDER BY id DESC
            LIMIT 50
            """
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/resend/status", methods=["GET"])
def resend_status():
    config = _load_resend_config()
    from_email = config.get("FROM_EMAIL", "")
    key_exists = bool(config.get("RESEND_API_KEY"))
    return jsonify(
        {
            "configured": key_exists and bool(from_email),
            "has_api_key": key_exists,
            "from_email": from_email,
            "sender_domain": from_email.split("@", 1)[1] if "@" in from_email else "",
        }
    )


@app.route("/api/resend/test", methods=["POST"])
def resend_test_email():
    data = request.get_json(silent=True) or {}
    to_email = (data.get("to_email") or "").strip().lower()
    if not to_email:
        return jsonify({"error": "to_email is required"}), 400

    subject = "[Dozenko] Test ket noi Resend"
    html = (
        "<h3>Ket noi Resend thanh cong</h3>"
        "<p>Neu ban nhan duoc email nay, domain va API key da hoat dong dung.</p>"
        f"<p>Thoi gian: {now_iso()}</p>"
    )
    ok, detail = _send_resend_email(to_email=to_email, subject=subject, html=html)
    if not ok:
        return jsonify({"ok": False, "error": detail}), 502
    return jsonify({"ok": True, "message_id": detail})


@app.route("/api/email-sequences", methods=["GET"])
def list_email_sequences():
    """View all email sequences (for admin/testing)"""
    with closing(get_connection()) as con:
        rows = con.execute(
            """
            SELECT
              id,
              customer_id,
              customer_email,
              customer_name,
              email1_sent,
              email1_sent_at,
              email2_sent,
              email2_scheduled_at,
              email2_sent_at,
              email3_sent,
              email3_scheduled_at,
              email3_sent_at,
              is_test_mode,
              created_at
            FROM email_sequences
            ORDER BY id DESC
            LIMIT 50
            """
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/email-sequences/<int:seq_id>", methods=["GET"])
def get_email_sequence(seq_id: int):
    """Get a specific email sequence (for debugging)"""
    with closing(get_connection()) as con:
        row = con.execute(
            """
            SELECT *
            FROM email_sequences
            WHERE id = ?
            """,
            (seq_id,)
        ).fetchone()
    if not row:
        return jsonify({"error": "sequence not found"}), 404
    return jsonify(row_to_dict(row))


@app.route("/api/test-email-sequence", methods=["POST"])
def test_email_sequence():
    """Test email sequence by sending all 3 emails immediately"""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    name = (data.get("name") or "Test Customer").strip()
    
    if not email:
        return jsonify({"error": "email is required"}), 400
    
    # Create a temporary customer for testing
    phone = "0123456789"
    with closing(get_connection()) as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO customers(name, phone, email, zalo, signup_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, phone, email, phone, now_iso())
        )
        con.commit()
        row = cur.execute(
            "SELECT id FROM customers WHERE phone = ?", (phone,)
        ).fetchone()
        customer_id = row["id"]
    
    # Send all 3 emails immediately
    ok, msg = _send_all_emails_immediately(customer_id, email, name)
    if not ok:
        return jsonify({"ok": False, "error": msg}), 502
    
    return jsonify({
        "ok": True,
        "message": msg,
        "customer_id": customer_id,
        "email": email
    })


@app.route("/api/orders/<int:order_id>/confirm-payment", methods=["POST"])
def confirm_payment(order_id: int):
    """Admin endpoint to confirm payment received and update order status to success"""
    with closing(get_connection()) as con:
        cur = con.cursor()
        existing = cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not existing:
            return jsonify({"error": "order not found"}), 404
        
        cur.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            ("success", order_id),
        )
        con.commit()
    
    with closing(get_connection()) as con:
        row = con.execute(
            """
            SELECT
              o.id,
              o.customer_id,
              o.product_id,
              o.amount,
              o.status,
              o.order_date,
              c.name AS customer_name,
              c.phone AS customer_phone,
              p.name AS product_name,
              p.type AS product_type
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            JOIN products p ON p.id = o.product_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()
    backup_db_to_github_async()
    return jsonify(row_to_dict(row))


# Initialize database
_ensure_db_file()
restore_db_from_github()
init_db()


# Initialize background scheduler for email sequences
def init_scheduler() -> None:
    """Initialize APScheduler for background email jobs"""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _process_pending_email_sequences,
        trigger=IntervalTrigger(minutes=1),
        id="email_sequence_job",
        name="Process pending email sequences",
        replace_existing=True,
    )
    scheduler.add_job(
        backup_db_to_github,
        trigger=IntervalTrigger(minutes=3),
        id="db_backup_job",
        name="Backup brain.db to GitHub",
        replace_existing=True,
    )
    try:
        scheduler.start()
        print("✅ Email sequence scheduler started")
    except Exception as e:
        print(f"⚠️  Scheduler already running or error: {e}")


# Avoid starting scheduler in debug reload
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
    init_scheduler()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
