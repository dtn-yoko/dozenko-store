from __future__ import annotations

import sqlite3
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

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


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
                zalo TEXT,
                signup_date TEXT NOT NULL
            )
            """
        )

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

        con.commit()


@app.route("/")
def root():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/admin")
def admin_page():
    return send_from_directory(BASE_DIR, "admin.html")


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
    phone = (data.get("phone") or "").strip()
    zalo = (data.get("zalo") or phone).strip()

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not phone:
        return jsonify({"error": "phone is required"}), 400

    with closing(get_connection()) as con:
        cur = con.cursor()
        existing = cur.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
        if existing:
            return jsonify(row_to_dict(existing)), 200

        cur.execute(
            """
            INSERT INTO customers(name, phone, zalo, signup_date)
            VALUES (?, ?, ?, ?)
            """,
            (name, phone, zalo, now_iso()),
        )
        customer_id = cur.lastrowid
        con.commit()
        row = cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
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
        phone = (data.get("phone", existing["phone"]) or "").strip()
        zalo = (data.get("zalo", existing["zalo"]) or "").strip()

        if not name or not phone:
            return jsonify({"error": "name and phone are required"}), 400

        duplicate = cur.execute(
            "SELECT id FROM customers WHERE phone = ? AND id != ?", (phone, customer_id)
        ).fetchone()
        if duplicate:
            return jsonify({"error": "phone already exists"}), 409

        cur.execute(
            "UPDATE customers SET name = ?, phone = ?, zalo = ? WHERE id = ?",
            (name, phone, zalo, customer_id),
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
    ref_code = (data.get("referenceCode") or "").strip()
    if not ref_code:
        return jsonify({"error": "missing referenceCode"}), 400
    
    try:
        order_id = int(ref_code.split(":")[-1])
    except (ValueError, IndexError):
        return jsonify({"error": "invalid referenceCode format"}), 400
    
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
    
    return jsonify({"ok": True, "order_id": order_id}), 200


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
    
    return webhook_sepay_helper(data)


@app.route("/api/webhook/sepay/test/<int:order_id>", methods=["POST"])
def webhook_sepay_test(order_id: int):
    """Test endpoint - simulates SePay webhook for testing"""
    data = {"referenceCode": f"order_id:{order_id}"}
    return webhook_sepay_helper(data)


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