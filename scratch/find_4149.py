import sqlite3

for db in ['data/warehouse.db', 'data/smar_inventory.db']:
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '%fts%';")
    tables = [t[0] for t in c.fetchall()]
    for t in tables:
        c.execute(f'PRAGMA table_info("{t}");')
        cols = [col[1] for col in c.fetchall()]
        for col in cols:
            try:
                c.execute(f'SELECT * FROM "{t}" WHERE CAST("{col}" AS TEXT) = "4149" LIMIT 5;')
                rows = c.fetchall()
                if rows:
                    print(f'Match in {db} -> {t}.{col}:', rows)
            except Exception:
                pass
