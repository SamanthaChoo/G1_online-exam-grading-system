#!/usr/bin/env python3
"""Quick database initialization and seeding script."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "online_exam_fastapi"))

# Change to the online_exam_fastapi directory for relative paths
os.chdir(os.path.join(os.path.dirname(__file__), "online_exam_fastapi"))

from datetime import datetime, timedelta
from sqlmodel import Session
from app.database import engine, create_db_and_tables
from app.models import (
    Student, User, Course, Enrollment, Exam, ExamQuestion, 
    ExamAttempt, EssayAnswer
)

# Create tables
print("Creating database tables...")
create_db_and_tables()

with Session(engine) as session:
    # Check if data already exists
    existing_course = session.exec(
        from sqlmodel import select
        select(Course).where(Course.code == "CS101")
    ).first()
    
    if existing_course:
        print("Database already seeded, skipping...")
    else:
        # Create a course
        course = Course(code="CS101", name="Introduction to Programming", description="Learn the basics")
        session.add(course)
        session.commit()
        session.refresh(course)
        print(f"Created course: {course.name}")
    
    # Create a student
    student = Student(name="Alice Tan", email="alice@example.com", matric_no="A001")
    session.add(student)
    session.commit()
    session.refresh(student)
    print(f"Created student: {student.name}")
    
    # Enroll student in course
    enrollment = Enrollment(course_id=course.id, student_id=student.id)
    session.add(enrollment)
    session.commit()
    print(f"Enrolled {student.name} in {course.name}")
    
    # Create an exam
    now = datetime.utcnow()
    exam = Exam(
        title="Midterm Exam",
        subject="Programming",
        duration_minutes=60,
        course_id=course.id,
        status="completed",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=1)
    )
    session.add(exam)
    session.commit()
    session.refresh(exam)
    print(f"Created exam: {exam.title}")
    
    # Create exam questions
    q1 = ExamQuestion(
        exam_id=exam.id,
        question_text="Explain the concept of variables",
        max_marks=10
    )
    q2 = ExamQuestion(
        exam_id=exam.id,
        question_text="Describe loops in programming",
        max_marks=15
    )
    session.add(q1)
    session.add(q2)
    session.commit()
    session.refresh(q1)
    session.refresh(q2)
    print(f"Created 2 questions for exam")
    
    # Create an exam attempt
    attempt = ExamAttempt(
        exam_id=exam.id,
        student_id=student.id,
        status="submitted",
        submitted_at=now - timedelta(hours=1)
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    print(f"Created attempt for {student.name}")
    
    # Create essay answers
    ans1 = EssayAnswer(
        attempt_id=attempt.id,
        question_id=q1.id,
        answer_text="Variables are containers for storing data values.",
        marks_awarded=None,
        grader_feedback=None
    )
    ans2 = EssayAnswer(
        attempt_id=attempt.id,
        question_id=q2.id,
        answer_text="Loops allow us to execute code multiple times.",
        marks_awarded=None,
        grader_feedback=None
    )
    session.add(ans1)
    session.add(ans2)
    session.commit()
    print(f"Created 2 essay answers")
    
    # Create a user (lecturer)
    user = User(
        name="Dr. John Smith",
        email="john@example.com",
        password_hash="hashed_password",
        role="lecturer"
    )
    session.add(user)
    session.commit()
    print(f"Created user: {user.name}")

print("\nDatabase seeding completed!")
