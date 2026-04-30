import sqlite3
from pathlib import Path

base_dir = Path(__file__).resolve().parents[1]
data_dir = base_dir / "data"
data_dir.mkdir(parents=True, exist_ok=True)
db_path = data_dir / "app.db"

print(f"DB path: {db_path}")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("Tables:", tables)

if 'users' in tables:
    cursor.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in cursor.fetchall()]
    print("Users columns:", cols)
    if 'token_version' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
        conn.commit()
        print("Added token_version column")
    else:
        print("token_version already exists")
else:
    print("users table not found")

conn.close()
print("Done")
