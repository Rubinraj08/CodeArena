import sqlite3
import os

db_paths = [
    r'c:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New\C655 Gamified New\CodeArena\instance\codearena.db',
    r'c:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New\C655 Gamified New\CodeArena\codearena.db',
    r'c:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New\codearena.db'
]

results = []
for p in db_paths:
    if os.path.exists(p):
        try:
            conn = sqlite3.connect(p)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            u_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM tasks")
            t_count = cursor.fetchone()[0]
            size = os.path.getsize(p)
            results.append(f"PATH: {p}\nUSERS: {u_count} | TASKS: {t_count} | SIZE: {size}")
            conn.close()
        except Exception as e:
            results.append(f"PATH: {p}\nERROR: {e}")
    else:
        results.append(f"PATH: {p}\nNOT FOUND")

with open('db_audit_report.txt', 'w') as f:
    f.write('\n\n'.join(results))
