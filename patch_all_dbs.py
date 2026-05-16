import os
import sqlite3

def patch_db(db_path):
    print(f"Patching: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(submissions)")
        cols = [c[1] for c in cursor.fetchall()]
        
        if not cols:
            print("  [submissions table not found]")
            conn.close()
            return

        added = []
        for col in ['ai_analysis', 'violation_reason', 'violation_status']:
            if col not in cols:
                try:
                    cursor.execute(f"ALTER TABLE submissions ADD COLUMN {col} TEXT")
                    added.append(col)
                except Exception as e:
                    print(f"  [Error adding {col}: {e}]")
        
        if added:
            conn.commit()
            print(f"  Added: {', '.join(added)}")
        else:
            print("  [All columns already exist]")
            
        conn.close()
    except Exception as e:
        print(f"  [Fatal error patching: {e}]")

root = r'C:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New'
for r, d, files in os.walk(root):
    for f in files:
        if f.lower() == 'codearena.db':
            patch_db(os.path.join(r, f))
