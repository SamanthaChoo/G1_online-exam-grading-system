"""
Sample Data Seeder for Testing Sprint 1 Features
Run this script to populate the database with test data

Usage:
    python seed_data.py
"""

from datetime import datetime
from sqlmodel import Session

try:
    from app.database import engine, create_db_and_tables
    from app.models import Student, Exam, EssayQuestion
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from app.database import engine, create_db_and_tables
    from app.models import Student, Exam, EssayQuestion


def seed_database():
    """Create sample data for testing"""
    
    # Create tables
    print("Creating database tables...")
    create_db_and_tables()
    
    with Session(engine) as session:
        # Check if data already exists
        existing_students = session.query(Student).first()
        if existing_students:
            print("Database already contains data. Skipping seed.")
            return
        
        print("Seeding database with sample data...")
        
        # Create sample students
        students = [
            Student(id=1, name="Alice Johnson", email="alice@example.com"),
            Student(id=2, name="Bob Smith", email="bob@example.com"),
            Student(id=3, name="Charlie Brown", email="charlie@example.com"),
            Student(id=4, name="Diana Prince", email="diana@example.com"),
            Student(id=5, name="Eve Williams", email="eve@example.com"),
        ]
        
        for student in students:
            session.add(student)
        
        print(f"✓ Created {len(students)} sample students")
        
        # Create sample exams
        exams = [
            Exam(
                id=1,
                title="Software Engineering Midterm",
                description="Topics: SDLC, Agile, Design Patterns",
                duration_minutes=2,
                created_at=datetime.now()
            ),
            Exam(
                id=2,
                title="Database Systems Final",
                description="Topics: SQL, Normalization, Transactions",
                duration_minutes=120,
                created_at=datetime.now()
            ),
            Exam(
                id=3,
                title="Web Development Quiz",
                description="Topics: HTML, CSS, JavaScript, FastAPI",
                duration_minutes=60,
                created_at=datetime.now()
            ),
        ]
        
        for exam in exams:
            session.add(exam)
        
        print(f"✓ Created {len(exams)} sample exams")
        
        # Create sample essay questions for Exam 1
        essay_questions_exam1 = [
            EssayQuestion(
                exam_id=1,
                question_text="Explain the key differences between Waterfall and Agile methodologies. Discuss the advantages and disadvantages of each approach.",
                max_marks=20,
                created_at=datetime.now()
            ),
            EssayQuestion(
                exam_id=1,
                question_text="Describe the SOLID principles in object-oriented design. Provide an example for each principle.",
                max_marks=25,
                created_at=datetime.now()
            ),
            EssayQuestion(
                exam_id=1,
                question_text="What is Continuous Integration/Continuous Deployment (CI/CD)? Explain its importance in modern software development.",
                max_marks=15,
                created_at=datetime.now()
            ),
        ]
        
        # Create sample essay questions for Exam 2
        essay_questions_exam2 = [
            EssayQuestion(
                exam_id=2,
                question_text="Explain database normalization and describe the First, Second, and Third Normal Forms with examples.",
                max_marks=30,
                created_at=datetime.now()
            ),
            EssayQuestion(
                exam_id=2,
                question_text="Discuss ACID properties in database transactions. Why are they important for data integrity?",
                max_marks=20,
                created_at=datetime.now()
            ),
        ]
        
        all_questions = essay_questions_exam1 + essay_questions_exam2
        for question in all_questions:
            session.add(question)
        
        print(f"✓ Created {len(all_questions)} sample essay questions")
        
        # Commit all changes
        session.commit()
        
        print("\n" + "="*60)
        print("✅ Database seeded successfully!")
        print("="*60)
        print("\nYou can now test Sprint 1 features:")
        print("\n1. Add Essay Questions:")
        print("   http://127.0.0.1:8000/essays/1/add")
        print("\n2. View Essay Questions:")
        print("   http://127.0.0.1:8000/essays/1/view")
        print("\n3. Take Exam (as student):")
        print("   http://127.0.0.1:8000/exam/1/start?student_id=1")
        print("\n4. View Submissions (after taking exam):")
        print("   http://127.0.0.1:8000/grading/1/submissions")
        print("\n" + "="*60)


if __name__ == "__main__":
    seed_database()
