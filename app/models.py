"""
SQLModel database models for Online Examination & Grading System
Sprint 1: Essay Questions, Submissions, and Exam Attempts
"""

from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, UniqueConstraint


# ====================================================
# EXISTING MODELS (Assumed from team members)
# ====================================================

class Student(SQLModel, table=True):
    """Student entity - managed by another team member"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    # Additional fields managed by auth team member


class Exam(SQLModel, table=True):
    """Exam entity - managed by another team member"""
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    duration_minutes: int  # Exam duration in minutes
    created_at: datetime = Field(default_factory=datetime.now)
    # Additional fields managed by exam creation team member


# ====================================================
# SPRINT 1 MODELS - MY RESPONSIBILITY
# ====================================================

class EssayQuestion(SQLModel, table=True):
    """
    Essay/Long-answer question entity.
    User Story 1: Create Essay Questions
    
    Sprint 2 Enhancement: Add difficulty level, topic tags
    """
    __tablename__ = "essayquestion"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exam.id", index=True)
    question_text: str = Field(min_length=1)
    max_marks: int = Field(gt=0)  # Must be positive
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Sprint 2: Add question_order, topic, difficulty_level


class EssaySubmission(SQLModel, table=True):
    """
    Student's essay answer submission.
    User Story 2: Manual Grade Essay Questions
    
    Sprint 2 Enhancement: Add draft saving, word count, plagiarism check
    """
    __tablename__ = "essaysubmission"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", "question_id", 
                        name="uq_essay_submission"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exam.id", index=True)
    student_id: int = Field(foreign_key="student.id", index=True)
    question_id: int = Field(foreign_key="essayquestion.id", index=True)
    answer_text: str
    submitted_at: datetime = Field(default_factory=datetime.now)
    
    # Grading fields (populated by lecturer during manual grading)
    marks_awarded: Optional[int] = None
    graded_at: Optional[datetime] = None
    grader_comments: Optional[str] = None
    
    # Sprint 2: Add is_draft, word_count, plagiarism_score


class ExamAttempt(SQLModel, table=True):
    """
    Tracks student exam attempts.
    User Story 3: Auto Submit When Time Ends
    User Story 4: One Attempt Enforcement
    
    Ensures:
    - One attempt per student per exam
    - Auto-submission when timer expires
    - Prevents retake after submission
    
    Sprint 2 Enhancement: Add pause/resume, proctoring data
    """
    __tablename__ = "examattempt"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", 
                        name="uq_exam_attempt"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exam.id", index=True)
    student_id: int = Field(foreign_key="student.id", index=True)
    
    # Timing fields
    started_at: datetime = Field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    remaining_seconds: Optional[int] = None  # For pause/resume in Sprint 2
    
    # Submission tracking
    submitted: bool = Field(default=False)  # Manual submit clicked
    auto_submitted: bool = Field(default=False)  # Timer expired
    
    # Sprint 2: Add ip_address, browser_fingerprint, webcam_snapshots
