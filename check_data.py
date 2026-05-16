import sqlite3
import os

db_paths = [
    r'c:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New\C655 Gamified New\CodeArena\instance\codearena.db',
    r'c:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New\C655 Gamified New\CodeArena\codearena.db',
    r'c:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New\CodeArena\codearena.db'
]

for p in db_paths:
    if os.path.exists(p):
        try:
            conn = sqlite3.connect(p)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            size = os.path.getsize(p)
            print(f"DB: {p} | Users: {count} | Size: {size}")
            conn.close()
        except Exception as e:
            print(f"DB: {p} | Error: {e}")
    else:
        print(f"DB: {p} | Not found")
