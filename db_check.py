import sqlite3
import os

db_path = 'instance/codearena.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute('SELECT violation_reason FROM submissions LIMIT 1')
    res = cursor.fetchone()
    print(f"Success: {res}")
except Exception as e:
    print(f"Error querying violation_reason: {e}")

conn.close()
