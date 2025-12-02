"""
Migration script to rename 'metadata' column to 'activity_metadata' in examactivitylog table.

This fixes the database schema mismatch after renaming the field in the ExamActivityLog model.

Usage:
    python migrate_activity_log.py
"""

import sqlite3
from pathlib import Path

def migrate_database():
    """Migrate the examactivitylog table to use activity_metadata instead of metadata."""
    
    db_path = Path("online_exam.db")
    if not db_path.exists():
        print("Database file not found. Creating fresh database...")
        print("Please restart your FastAPI server to create tables with correct schema.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if the old column exists
        cursor.execute("PRAGMA table_info(examactivitylog)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'metadata' in columns and 'activity_metadata' not in columns:
            print("Migrating examactivitylog table: renaming 'metadata' to 'activity_metadata'...")
            
            # SQLite doesn't support ALTER TABLE RENAME COLUMN in older versions
            # We need to create a new table, copy data, drop old table, and rename
            
            # Step 1: Create new table with correct schema
            cursor.execute("""
                CREATE TABLE examactivitylog_new (
                    id INTEGER PRIMARY KEY,
                    attempt_id INTEGER,
                    exam_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    activity_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    activity_metadata TEXT,
                    severity TEXT NOT NULL DEFAULT 'low',
                    FOREIGN KEY(attempt_id) REFERENCES examattempt(id),
                    FOREIGN KEY(exam_id) REFERENCES exam(id),
                    FOREIGN KEY(student_id) REFERENCES student(id)
                )
            """)
            
            # Step 2: Copy data from old table to new table
            cursor.execute("""
                INSERT INTO examactivitylog_new 
                (id, attempt_id, exam_id, student_id, activity_type, timestamp, activity_metadata, severity)
                SELECT id, attempt_id, exam_id, student_id, activity_type, timestamp, metadata, severity
                FROM examactivitylog
            """)
            
            # Step 3: Drop old table
            cursor.execute("DROP TABLE examactivitylog")
            
            # Step 4: Rename new table to old name
            cursor.execute("ALTER TABLE examactivitylog_new RENAME TO examactivitylog")
            
            conn.commit()
            print("✓ Migration completed successfully!")
            print("  Column 'metadata' has been renamed to 'activity_metadata'")
            
        elif 'activity_metadata' in columns:
            print("✓ Database already has 'activity_metadata' column. No migration needed.")
            
        elif 'metadata' not in columns and 'activity_metadata' not in columns:
            print("⚠ Table 'examactivitylog' doesn't exist yet.")
            print("  It will be created with correct schema when you restart the server.")
            
        else:
            print("⚠ Table structure is unexpected. Please check manually.")
            print(f"  Columns found: {columns}")
            
    except sqlite3.Error as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Exam Activity Log Migration Script")
    print("=" * 60)
    print()
    migrate_database()
    print()
    print("=" * 60)

