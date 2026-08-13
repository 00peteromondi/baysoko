import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'db.sqlite3'
if not DB.exists():
    print('DB_NOT_FOUND')
    raise SystemExit(1)

conn = sqlite3.connect(str(DB))
cur = conn.cursor()
cur.execute("PRAGMA foreign_keys = ON")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='listings_listing_favorited_by'")
if cur.fetchone():
    print('TABLE_ALREADY_EXISTS')
else:
    cur.execute('''
    CREATE TABLE listings_listing_favorited_by (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        UNIQUE(listing_id, user_id)
    )
    ''')
    conn.commit()
    print('TABLE_CREATED')

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='listings_listing_favorited_by'")
print('VERIFY', 'FOUND' if cur.fetchone() else 'MISSING')
conn.close()
