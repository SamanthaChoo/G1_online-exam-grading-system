import sqlite3
from typing import Optional, List, Dict, Any

# Database connection
DATABASE = "database.db"


def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create essay_questions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS essay_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            max_marks INTEGER NOT NULL
        )
    """)
    
    # Create essay_grades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS essay_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            student_answer TEXT,
            marks_awarded INTEGER,
            FOREIGN KEY (question_id) REFERENCES essay_questions(id)
        )
    """)
    
    conn.commit()
    conn.close()


def create_question(question_text: str, max_marks: int) -> int:
    """
    Create a new essay question.
    
    Args:
        question_text: The text of the question
        max_marks: Maximum marks for the question
        
    Returns:
        The ID of the created question
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO essay_questions (question_text, max_marks) VALUES (?, ?)",
        (question_text, max_marks)
    )
    question_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return question_id


def get_question(question_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific essay question by ID.
    
    Args:
        question_id: The ID of the question
        
    Returns:
        Dictionary containing question data or None if not found
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM essay_questions WHERE id = ?",
        (question_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_all_questions() -> List[Dict[str, Any]]:
    """
    Get all essay questions.
    
    Returns:
        List of dictionaries containing all questions
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM essay_questions ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def save_grade(question_id: int, student_id: str, student_answer: str, marks_awarded: int) -> int:
    """
    Save or update a grade for an essay question.
    
    Args:
        question_id: The ID of the question
        student_id: The ID of the student
        student_answer: The student's answer text
        marks_awarded: Marks awarded to the student
        
    Returns:
        The ID of the grade record
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if a grade already exists for this question and student
    cursor.execute(
        "SELECT id FROM essay_grades WHERE question_id = ? AND student_id = ?",
        (question_id, student_id)
    )
    existing = cursor.fetchone()
    
    if existing:
        # Update existing grade
        cursor.execute(
            """UPDATE essay_grades 
               SET student_answer = ?, marks_awarded = ? 
               WHERE question_id = ? AND student_id = ?""",
            (student_answer, marks_awarded, question_id, student_id)
        )
        grade_id = existing[0]
    else:
        # Insert new grade
        cursor.execute(
            """INSERT INTO essay_grades 
               (question_id, student_id, student_answer, marks_awarded) 
               VALUES (?, ?, ?, ?)""",
            (question_id, student_id, student_answer, marks_awarded)
        )
        grade_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return grade_id


def get_grade(question_id: int, student_id: str = "sample_student") -> Optional[Dict[str, Any]]:
    """
    Get a grade for a specific question and student.
    
    Args:
        question_id: The ID of the question
        student_id: The ID of the student (default: "sample_student")
        
    Returns:
        Dictionary containing grade data or None if not found
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM essay_grades WHERE question_id = ? AND student_id = ?",
        (question_id, student_id)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


# Initialize database on module import
init_db()
