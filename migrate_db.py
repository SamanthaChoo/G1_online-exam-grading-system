#!/usr/bin/env python3
"""Database migration script to add missing columns."""
import sqlite3

db_path = "online_exam_fastapi/online_exam.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# List all tables
print("Existing tables:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    print(f"  - {table[0]}")

# Try to add columns to examquestion
try:
    cursor.execute("PRAGMA table_info(examquestion)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"\nexamquestion columns: {columns}")
    
except Exception as e:
    print(f"examquestion error: {e}")

# Try to add columns to essayanswer
try:
    cursor.execute("PRAGMA table_info(essayanswer)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"\nessayanswer columns: {columns}")
    
    if "grader_feedback" not in columns:
        print("Adding grader_feedback to essayanswer...")
        cursor.execute("ALTER TABLE essayanswer ADD COLUMN grader_feedback TEXT")
        print("✓ Added")
except Exception as e:
    print(f"essayanswer error: {e}")

conn.commit()
conn.close()
print("\nMigration complete!")
