import sqlite3
import os

def patch_submissions_table(db_path):
    print(f"Checking database: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if 'submissions' table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='submissions'")
        if not cursor.fetchone():
            print(f"  [submissions table not found, skipping]")
            conn.close()
            return
            
        # Check existing columns
        cursor.execute("PRAGMA table_info(submissions)")
        existing_cols = [col[1] for col in cursor.fetchall()]
        
        target_cols = ['ai_analysis', 'violation_reason', 'violation_status']
        for col in target_cols:
            if col not in existing_cols:
                print(f"  Adding missing column: {col}")
                try:
                    cursor.execute(f"ALTER TABLE submissions ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError as e:
                    print(f"  [Error adding {col}: {e}]")
        
        conn.commit()
        conn.close()
        print(f"  [Patch complete for {db_path}]")
    except Exception as e:
        print(f"  [Fatal error patching {db_path}: {e}]")

if __name__ == "__main__":
    root_dir = r"C:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New"
    for root, _, files in os.walk(root_dir):
        for f in files:
            if f.lower() == "codearena.db":
                patch_submissions_table(os.path.join(root, f))
