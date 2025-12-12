"""SQLModel models for the Online Exam & Grading System."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Student(SQLModel, table=True):
    """Basic student record used for enrollments and linking to user accounts."""

    __table_args__ = (
        UniqueConstraint("matric_no", name="uq_student_matric_no"),
        UniqueConstraint("email", name="uq_student_email"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    matric_no: str
    # Sprint 2: optional link to a user account (when the student registers)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Optional basic info
    program: Optional[str] = None  # e.g., "SWE", "BIM"
    year_of_study: Optional[int] = None  # e.g., 1, 2, 3, 4
    phone_number: Optional[str] = None

    # Future exam-related fields
    gpa: Optional[float] = None

    # Relationships intentionally omitted for Sprint 1 to avoid SQLAlchemy 2.x
    # type-hint issues. We'll re-introduce them in Sprint 2 when we add real
    # users/roles and more complex navigation.


class Course(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("code", name="uq_course_code"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # See comment in Student: we rely on foreign keys + explicit queries
    # instead of SQLAlchemy Relationship() helpers for Sprint 1.


class Exam(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    subject: str
    duration_minutes: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    course_id: Optional[int] = Field(default=None, foreign_key="course.id")
    instructions: Optional[str] = None
    status: str = Field(default="draft")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Access the course via explicit queries using course_id


class Enrollment(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("course_id", "student_id", name="uq_course_student"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id")
    student_id: int = Field(foreign_key="student.id")
    enrolled_at: datetime = Field(default_factory=datetime.utcnow)


# --- Essay-based exam models (Sprint 1 implementation) ---


class ExamQuestion(SQLModel, table=True):
    """An essay question belonging to an exam."""

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exam.id")
    question_text: str
    max_marks: int


class ExamAttempt(SQLModel, table=True):
    """Tracks an attempt by a student for an exam."""

    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exam.id")
    student_id: int = Field(foreign_key="student.id")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    status: str = Field(default="in_progress")  # in_progress | submitted | timed_out
    is_final: int = Field(default=0)  # 0/1


class EssayAnswer(SQLModel, table=True):
    """Answer to an essay question within an attempt."""

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="examattempt.id")
    question_id: int = Field(foreign_key="examquestion.id")
    answer_text: Optional[str] = None
    marks_awarded: Optional[float] = None
    grader_feedback: Optional[str] = None


class CourseLecturer(SQLModel, table=True):
    """Junction table for many-to-many relationship between Course and Lecturer (User with role='lecturer')."""

    __table_args__ = (
        UniqueConstraint("course_id", "lecturer_id", name="uq_course_lecturer"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id")
    lecturer_id: int = Field(foreign_key="user.id")
    assigned_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    """Application user that can log in and own a role (admin / lecturer / student)."""

    __table_args__ = (UniqueConstraint("email", name="uq_user_email"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str  # must be unique
    password_hash: str
    role: str = Field(default="student")  # "admin", "lecturer", "student"
    # Optional link back to a Student record for student accounts
    student_id: Optional[int] = Field(default=None, foreign_key="student.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Lecturer-specific fields
    title: Optional[str] = None  # Dr., Prof., Assoc. Prof., Mr., Ms., Mrs., Ir., Ts.
    staff_id: Optional[str] = None  # Unique staff/employee ID (for lecturers)
    phone: Optional[str] = None  # Contact number
    last_login: Optional[datetime] = None  # Updated after login
    status: str = Field(default="active")  # active, suspended


class PasswordResetToken(SQLModel, table=True):
    """Password reset tokens for email-based reset flow."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    token: str
    expires_at: datetime
    used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PasswordResetOTP(SQLModel, table=True):
    """Password reset OTP codes (6-digit) for email-based reset flow."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    otp_code: str  # 6-digit code
    expires_at: datetime
    used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ===================== SPRINT 1 MCQ MODELS =====================


class MCQQuestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exam.id")
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str


class MCQAnswer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    exam_id: int = Field(foreign_key="exam.id")
    question_id: int = Field(foreign_key="mcqquestion.id")
    selected_option: Optional[str] = None
    saved_at: datetime = Field(default_factory=datetime.utcnow)


class MCQResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.id")
    exam_id: int = Field(foreign_key="exam.id")
    score: int
    total_questions: int
    graded_at: datetime


# ===================== EXAM SECURITY & ANTI-CHEATING MODELS =====================


class ExamActivityLog(SQLModel, table=True):
    """Logs suspicious activities and anti-cheating events during exams."""

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: Optional[int] = Field(default=None, foreign_key="examattempt.id")
    exam_id: int = Field(foreign_key="exam.id")
    student_id: int = Field(foreign_key="student.id")
    activity_type: str  # e.g., "tab_switch", "right_click", "copy_attempt", "paste_attempt", "devtools_attempt", "fullscreen_exit"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    activity_metadata: Optional[str] = Field(
        default=None
    )  # JSON string for additional data (e.g., tab switch count, key pressed)
    severity: str = Field(default="low")  # low, medium, high
