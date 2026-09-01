import sqlite3
import os

db_path = os.path.abspath('backend/data/drishtik.db')
print(f"DB Path: {db_path}")

if not os.path.exists(db_path):
    print("Database file does not exist at this path.")
else:
    conn = sqlite3.connect(db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    print(f"Tables: {tables}")
