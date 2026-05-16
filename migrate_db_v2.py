import sqlite3
import os

db_path = r'C:\Users\sriva\OneDrive\Desktop\projects\C655 Gamified New\C655 Gamified New\CodeArena\instance\codearena.db'

if not os.path.exists(db_path):
    print(f"ERROR: Database file not found at {db_path}")
    exit(1)

print(f"Connecting to database: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def add_column(name):
    try:
        cursor.execute(f"ALTER TABLE submissions ADD COLUMN {name} TEXT")
        print(f"Successfully added column: {name}")
    except sqlite3.OperationalError as e:
        print(f"Failed to add {name}: {e}")

add_column('violation_reason')
add_column('violation_status')

conn.commit()

# Final verification
cursor.execute("PRAGMA table_info(submissions)")
cols = [r[1] for r in cursor.fetchall()]
print(f"Final column list: {cols}")

conn.close()
