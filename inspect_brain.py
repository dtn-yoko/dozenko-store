import sqlite3
con = sqlite3.connect('brain.db')
cur = con.cursor()
print('tables:')
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(row[0])
print('---')
for tbl in ['brain','voice','brand_voice','notes','data']:
    try:
        print('TABLE', tbl)
        for row in cur.execute(f"SELECT * FROM {tbl} LIMIT 20"):
            print(row)
    except Exception as e:
        print('SKIP', tbl, e)
con.close()
