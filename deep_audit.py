import os
import sqlite3

# Possible database locations
root_dir = r"c:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New"
databases = []

for root, dirs, files in os.walk(root_dir):
    for f in files:
        if f.lower() == "codearena.db":
            databases.append(os.path.join(root, f))

print(f"Found {len(databases)} database(s):")
for db_path in databases:
    size = os.path.getsize(db_path)
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        
        user_count = 0
        task_count = 0
        if "users" in tables:
            user_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if "tasks" in tables:
            task_count = c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            
        print(f"--- {db_path} ---")
        print(f"Size: {size / 1024:.2f} KB")
        print(f"Tables: {', '.join(tables)}")
        print(f"Users: {user_count} | Tasks: {task_count}")
        conn.close()
    except Exception as e:
        print(f"--- {db_path} ---")
        print(f"Size: {size / 1024:.2f} KB")
        print(f"Error accessing: {e}")

print("\n--- End of Audit ---")
