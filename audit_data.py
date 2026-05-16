import os
import sqlite3

def audit_db(db_path):
    # print(f"Checking: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        
        counts = {}
        for t in ['users', 'tasks', 'submissions']:
            if t in tables:
                counts[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            else:
                counts[t] = 'N/A'
        
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(submissions)")
        cols = [col[1] for col in cursor.fetchall()]
        has_violation = 'violation_reason' in cols
        
        print(f"DB: {db_path}")
        print(f"  Users: {counts['users']} | Tasks: {counts['tasks']} | Submissions: {counts['submissions']}")
        print(f"  Violation Reason Column: {'YES' if has_violation else 'NO'}")
        print(f"  All Columns: {cols}")
        conn.close()
    except Exception as e:
        # print(f"  [Error auditing: {e}]")
        pass

root = r'C:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New'
for r, d, files in os.walk(root):
    for f in files:
        if f.lower() == 'codearena.db':
            audit_db(os.path.join(r, f))
