import sqlite3

con = sqlite3.connect('data/warehouse.db')
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '%fts%'")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    cur.execute(f'PRAGMA table_info("{t}")')
    cols = [(c[1], c[2]) for c in cur.fetchall()]
    cur.execute(f'SELECT count(*) FROM "{t}"')
    cnt = cur.fetchone()[0]
    print(f'{t} ({cnt:,} rows): {cols}')
