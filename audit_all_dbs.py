import os
import sqlite3

root = r'C:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New'
for r, d, files in os.walk(root):
    for f in files:
        if f.lower() == 'codearena.db':
            db_path = os.path.join(r, f)
            print(f"\nDB: {db_path}")
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('PRAGMA table_info(submissions)')
                cols = [col[1] for col in cursor.fetchall()]
                if not cols:
                    print("  [submissions table does not exist]")
                else:
                    print(f"  Columns: {', '.join(cols)}")
                conn.close()
            except Exception as e:
                print(f"  [Error: {e}]")
