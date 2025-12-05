#!/usr/bin/env python3
"""Script to remove allow_negative_marks column from database."""
import sqlite3

db_path = "online_exam_fastapi/online_exam.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # SQLite doesn't support DROP COLUMN directly in all versions
    # We'll use ALTER TABLE ... DROP COLUMN (SQLite 3.35.0+)
    print("Attempting to drop allow_negative_marks column...")
    cursor.execute("ALTER TABLE examquestion DROP COLUMN allow_negative_marks")
    print("✓ Successfully dropped allow_negative_marks column")
    conn.commit()
except Exception as e:
    print(f"Note: {e}")
    print("\nAlternative: Recreating table without the column...")
    try:
        # Create a temporary table with the old schema
        cursor.execute("""
            CREATE TABLE examquestion_new (
                id INTEGER PRIMARY KEY,
                exam_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                max_marks INTEGER NOT NULL,
                FOREIGN KEY (exam_id) REFERENCES exam(id)
            )
        """)
        
        # Copy data from old table
        cursor.execute("""
            INSERT INTO examquestion_new (id, exam_id, question_text, max_marks)
            SELECT id, exam_id, question_text, max_marks FROM examquestion
        """)
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE examquestion")
        cursor.execute("ALTER TABLE examquestion_new RENAME TO examquestion")
        
        conn.commit()
        print("✓ Successfully removed allow_negative_marks column")
    except Exception as e2:
        print(f"Error during table recreation: {e2}")
        conn.rollback()

conn.close()
print("Done!")
