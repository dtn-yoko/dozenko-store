import sqlite3

conn = sqlite3.connect('brain.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print('TABLES IN brain.db:', tables)
for t in tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = cursor.fetchone()[0]
        cursor.execute(f"PRAGMA table_info([{t}])")
        cols = [c[1] for c in cursor.fetchall()]
        print(f"\n  [{t}] - {count} rows")
        print(f"  Columns: {cols}")
        cursor.execute(f"SELECT * FROM [{t}] LIMIT 3")
        for r in cursor.fetchall():
            print(f"    {str(r)[:150]}")
    except Exception as e:
        print(f"  [{t}] ERROR: {e}")
conn.close()
