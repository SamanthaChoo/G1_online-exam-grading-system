"""SQLModel models for the Online Exam & Grading System."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    matric_no: str

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
    __table_args__ = (UniqueConstraint("course_id", "student_id", name="uq_course_student"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id")
    student_id: int = Field(foreign_key="student.id")
    enrolled_at: datetime = Field(default_factory=datetime.utcnow)

