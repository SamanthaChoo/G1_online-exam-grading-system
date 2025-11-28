"""
Seed script to add test data for pagination testing.
This script adds:
- 15 courses (to test course list pagination)
- 15 exams (to test exam list pagination)
- 15 students (to test student enrollment pagination)

Usage:
    python seed_pagination_data.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import uuid

# Add the parent directory to the path
repo_root = Path(__file__).resolve().parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app.database import engine, create_db_and_tables
from app.models import Course, Exam, Student, User, CourseLecturer, Enrollment
from sqlmodel import Session, select


def seed_pagination_data():
    """Create test data for pagination testing."""
    
    print("Creating database tables...")
    create_db_and_tables()
    
    with Session(engine) as session:
        print("\n" + "="*60)
        print("Seeding pagination test data...")
        print("="*60)
        
        # Check if we need to create a lecturer user
        lecturer = session.exec(select(User).where(User.role == "lecturer")).first()
        if not lecturer:
            lecturer = User(
                name="Test Lecturer",
                email="lecturer@example.com",
                password_hash="test_hash",
                role="lecturer",
                is_active=True,
            )
            session.add(lecturer)
            session.commit()
            session.refresh(lecturer)
            print(f"✓ Created lecturer user: {lecturer.email}")
        else:
            print(f"✓ Using existing lecturer: {lecturer.email}")
        
        # Create 15 courses
        print("\nCreating 15 courses...")
        courses = []
        for i in range(1, 16):
            course = Course(
                code=f"PAG{i:02d}",
                name=f"Pagination Test Course {i}",
                description=f"This is course number {i} for testing pagination functionality. It covers various topics related to software engineering and web development." if i % 2 == 0 else None,
            )
            session.add(course)
            courses.append(course)
        session.commit()
        for course in courses:
            session.refresh(course)
        print(f"✓ Created {len(courses)} courses")
        
        # Assign lecturer to all courses
        print("\nAssigning lecturer to courses...")
        for course in courses:
            course_lecturer = CourseLecturer(
                course_id=course.id,
                lecturer_id=lecturer.id,
            )
            session.add(course_lecturer)
        session.commit()
        print(f"✓ Assigned lecturer to {len(courses)} courses")
        
        # Create 15 students
        print("\nCreating 15 students...")
        students = []
        for i in range(1, 16):
            student = Student(
                name=f"Student {i:02d}",
                email=f"student{i:02d}@example.com",
                matric_no=f"MAT{i:04d}",
            )
            session.add(student)
            students.append(student)
        session.commit()
        for student in students:
            session.refresh(student)
        print(f"✓ Created {len(students)} students")
        
        # Enroll some students in the first course (for testing enrollment pagination)
        print("\nEnrolling students in first course...")
        enrollments = []
        for i in range(3):  # Enroll first 3 students
            enrollment = Enrollment(
                course_id=courses[0].id,
                student_id=students[i].id,
            )
            session.add(enrollment)
            enrollments.append(enrollment)
        session.commit()
        print(f"✓ Enrolled {len(enrollments)} students in course {courses[0].code}")
        
        # Create 15 exams (distributed across courses)
        print("\nCreating 15 exams...")
        exams = []
        base_time = datetime.now(timezone.utc).replace(microsecond=0)
        for i in range(1, 16):
            # Distribute exams across courses (some courses will have multiple exams)
            course_index = (i - 1) % len(courses)
            course = courses[course_index]
            
            start_time = base_time + timedelta(days=i, hours=9)
            end_time = start_time + timedelta(hours=2)
            
            exam = Exam(
                title=f"Exam {i:02d} - {course.code}",
                subject=f"Subject {i}",
                duration_minutes=60 + (i * 5),  # Varying durations
                course_id=course.id,
                start_time=start_time.replace(tzinfo=None),
                end_time=end_time.replace(tzinfo=None),
                instructions=f"Instructions for exam {i}. Please read carefully before starting." if i % 3 == 0 else None,
                status="draft" if i % 3 == 0 else ("scheduled" if i % 3 == 1 else "completed"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(exam)
            exams.append(exam)
        session.commit()
        for exam in exams:
            session.refresh(exam)
        print(f"✓ Created {len(exams)} exams")
        
        print("\n" + "="*60)
        print("Pagination test data seeded successfully!")
        print("="*60)
        print(f"\nSummary:")
        print(f"  - Courses: {len(courses)} (should show 2 pages)")
        print(f"  - Exams: {len(exams)} (distributed across courses)")
        print(f"  - Students: {len(students)} (should show 2 pages in enrollment)")
        print(f"  - Enrollments: {len(enrollments)} students in {courses[0].code}")
        print(f"\nYou can now test pagination:")
        print(f"  - Course list: http://127.0.0.1:8000/courses/")
        print(f"  - Exam list: http://127.0.0.1:8000/exams/course/{courses[0].id}")
        print(f"  - Student enrollment: http://127.0.0.1:8000/courses/{courses[0].id}/enroll")
        print("="*60 + "\n")


if __name__ == "__main__":
    try:
        seed_pagination_data()
    except Exception as e:
        print(f"\n❌ Error seeding data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

