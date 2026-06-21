from __future__ import annotations

import sqlite3
import re
import json
import os
import urllib.request
import urllib.error
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import hmac
import hashlib


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "brain.db"
RESEND_CONFIG_PATH = BASE_DIR / "resend_config.txt"

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def is_valid_vn_phone(phone: str) -> bool:
    # Accept local VN style: 10-11 digits.
    return bool(re.fullmatch(r"\d{10,11}", phone or ""))


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
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

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        parsed = json.loads(body) if body else {}
        return True, str(parsed.get("id", "sent"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="ignore")
        return False, f"HTTP {exc.code}: {err_body}"
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

    # Send welcome email after successful new customer creation.
    if email:
        _send_welcome_email(name, email)

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
              p.name AS product_name,
              p.type AS product_type
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            JOIN products p ON p.id = o.product_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()
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
    return jsonify(row_to_dict(row))
init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
