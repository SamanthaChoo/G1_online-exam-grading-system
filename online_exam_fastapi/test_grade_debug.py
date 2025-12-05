#!/usr/bin/env python3
"""Debug script to test grade_submit endpoint."""

import sys
sys.path.insert(0, "/app")

from sqlmodel import Session, create_engine, SQLModel, select
from app.database import get_session
from app.models import (
    ExamQuestion, EssayAnswer, ExamAttempt, Exam,
    User, Student, Course, Enrollment
)
from app.services.essay_service import grade_attempt
from app.database import sqlite_url

# Create engine and session
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
session = Session(engine)

# Test: Try to grade attempt_id=1
try:
    attempt = session.exec(select(ExamAttempt).where(ExamAttempt.id == 1)).first()
    print(f"Attempt 1: {attempt}")
    
    if attempt:
        # Get exam and questions
        exam = session.get(Exam, attempt.exam_id)
        print(f"Exam: {exam}")
        
        questions = session.exec(
            select(ExamQuestion).where(ExamQuestion.exam_id == attempt.exam_id)
        ).all()
        print(f"Questions in exam: {len(questions)}")
        for q in questions:
            print(f"  - Q{q.id}: {q.question_text[:50]}... (max_marks={q.max_marks})")
        
        # Check existing answers
        answers = session.exec(
            select(EssayAnswer).where(EssayAnswer.attempt_id == 1)
        ).all()
        print(f"Existing answers: {len(answers)}")
        for a in answers:
            print(f"  - A{a.id}: Q{a.question_id}, answer_text={a.answer_text is not None}, marks={a.marks_awarded}")
        
        # Try grading
        scores = [
            {"question_id": q.id, "marks": 5.0}
            for q in questions[:min(2, len(questions))]
        ]
        print(f"\nAttempting to grade with scores: {scores}")
        
        result = grade_attempt(session, 1, scores, [])
        print(f"Grade result: {result}")
        
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
