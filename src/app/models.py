"""
Database Models for Online Exam Grading System
Sprint 1: MCQ Questions + Auto-Grading + Exam Execution

Uses SQLModel for ORM with SQLite database
"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class Exam(SQLModel, table=True):
    """
    Exam model - represents an examination
    Pre-existing model from teammate's work
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    start_time: datetime
    duration_minutes: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MCQQuestion(SQLModel, table=True):
    """
    Multiple Choice Question model
    Each MCQ belongs to an exam and contains 4 options (A, B, C, D)
    """
    __tablename__ = "mcq_question"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exam.id")
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str  # 'A', 'B', 'C', or 'D'
    explanation: Optional[str] = None  # Optional explanation for correct answer
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StudentAnswer(SQLModel, table=True):
    """
    Student Answer model - stores student's selected answer for each question
    Auto-saved every 60 seconds during exam
    """
    __tablename__ = "student_answer"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int  # No FK since Sprint 1 has no authentication
    exam_id: int = Field(foreign_key="exam.id")
    question_id: int = Field(foreign_key="mcq_question.id")
    selected_option: str  # 'A', 'B', 'C', 'D', or empty if not answered
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExamResult(SQLModel, table=True):
    """
    Exam Result model - stores the final score after auto-grading
    Generated when student submits exam or time expires
    """
    __tablename__ = "exam_result"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int  # No FK since Sprint 1 has no authentication
    exam_id: int = Field(foreign_key="exam.id")
    score: float  # Percentage score (0-100)
    total_questions: int
    correct_answers: int
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
