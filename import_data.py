import sqlite3
import json
import sys
import io
from datetime import datetime

# Fix encoding cho Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_PATH = 'brain.db'
WAITLIST_PATH = r'C:\Users\Admin\Desktop\my-brain\waitlist.json'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 50)
print("IMPORT DATA VÀO BRAIN.DB")
print("=" * 50)

# ===== 1. IMPORT PRODUCTS =====
print("\n[1] Thêm sản phẩm thảm Dozenko...")

products = [
    {
        'name': 'Thảm Hoa Xanh Đại Dương',
        'type': 'physical',
        'price': 300000,
        'description': 'Thảm hoa thủ công, cánh hoa xanh navy & xanh phấn với nhụy trắng. Cotton cao cấp, đế chống trượt 3cm. Kích thước 50x120cm.',
        'quantity': 15
    },
    {
        'name': 'Thảm Hoa Xanh Lá Rừng',
        'type': 'physical',
        'price': 300000,
        'description': 'Thảm hoa thủ công, cánh hoa xanh tươi với nhụy vàng. Cotton cao cấp, đế chống trượt 3cm. Kích thước 50x120cm.',
        'quantity': 15
    },
    {
        'name': 'Thảm Hoa Cam Caramel',
        'type': 'physical',
        'price': 300000,
        'description': 'Thảm hoa thủ công, cánh hoa cam đất & vàng ấm. Cotton cao cấp, đế chống trượt 3cm. Kích thước 50x120cm.',
        'quantity': 15
    },
    {
        'name': 'Thảm Hoa Nâu Ấm',
        'type': 'physical',
        'price': 300000,
        'description': 'Thảm hoa thủ công, cánh hoa nâu socola & kem. Cotton cao cấp, đế chống trượt 3cm. Kích thước 50x120cm.',
        'quantity': 15
    },
    {
        'name': 'Combo 2 Tấm Thảm (Tùy Chọn Màu)',
        'type': 'physical',
        'price': 500000,
        'description': 'Combo 2 tấm thảm Dozenko, chọn màu tự do. Miễn phí vận chuyển.',
        'quantity': None  # NULL vì là combo, quản lý theo từng màu
    },
    {
        'name': 'Combo 3 Tấm Thảm (Tùy Chọn Màu)',
        'type': 'physical',
        'price': 700000,
        'description': 'Combo 3 tấm thảm Dozenko, chọn màu tự do. Miễn phí vận chuyển.',
        'quantity': None
    },
    {
        'name': 'Combo 4 Tấm Thảm (Tùy Chọn Màu)',
        'type': 'physical',
        'price': 840000,
        'description': 'Combo 4 tấm thảm Dozenko, chọn màu tự do. Miễn phí vận chuyển.',
        'quantity': None
    },
]

for p in products:
    cur.execute('''
        INSERT INTO products (name, type, price, description, quantity, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (p['name'], p['type'], p['price'], p['description'], p['quantity'], datetime.now().isoformat()))
    print(f"  ✓ Đã thêm: {p['name']} — {p['price']:,}đ — Tồn kho: {p['quantity']}")

conn.commit()

# ===== 2. IMPORT CUSTOMERS TỪ WAITLIST =====
print(f"\n[2] Import khách hàng từ waitlist.json...")

with open(WAITLIST_PATH, encoding='utf-8') as f:
    waitlist = json.load(f)

imported = 0
skipped = 0

for customer in waitlist:
    phone = customer.get('phone', '')
    # Kiểm tra trùng lặp theo số điện thoại
    cur.execute('SELECT id FROM customers WHERE phone = ?', (phone,))
    existing = cur.fetchone()
    if existing:
        print(f"  ⚠ Bỏ qua (đã tồn tại): {customer['name']} — {phone}")
        skipped += 1
        continue

    cur.execute('''
        INSERT INTO customers (name, phone, zalo, signup_date)
        VALUES (?, ?, ?, ?)
    ''', (customer['name'], phone, customer.get('zalo', phone), customer.get('time', datetime.now().isoformat())))
    imported += 1
    print(f"  ✓ Đã import: {customer['name']} — {phone}")

conn.commit()
print(f"\n  → Đã import: {imported} | Bỏ qua (trùng): {skipped}")

# ===== 3. KIỂM TRA KẾT QUẢ =====
print("\n" + "=" * 50)
print("KẾT QUẢ SAU KHI IMPORT:")
print("=" * 50)

cur.execute('SELECT COUNT(*) FROM products')
print(f"\n  📦 Sản phẩm: {cur.fetchone()[0]} records")
cur.execute('SELECT id, name, price, quantity FROM products')
for row in cur.fetchall():
    qty = str(row[3]) if row[3] is not None else "N/A (combo)"
    print(f"      [{row[0]}] {row[1]} — {row[2]:,}đ — Tồn: {qty}")

cur.execute('SELECT COUNT(*) FROM customers')
print(f"\n  👥 Khách hàng: {cur.fetchone()[0]} records")
cur.execute('SELECT id, name, phone FROM customers')
for row in cur.fetchall():
    print(f"      [{row[0]}] {row[1]} — {row[2]}")

cur.execute('SELECT COUNT(*) FROM orders')
print(f"\n  🛒 Đơn hàng: {cur.fetchone()[0]} records")

conn.close()
print("\n✅ HOÀN THÀNH! Database đã sẵn sàng.")
