import sys
from pathlib import Path
from datetime import datetime, timedelta

from sqlmodel import Session
import uuid


def _ensure_app_on_path():
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


def _fresh_db():
    _ensure_app_on_path()
    from app.database import create_db_and_tables

    create_db_and_tables()


def _unique_code(prefix: str = "COURSE") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}".upper()


class TestEnrollmentVisibilityConstraints:
    """Acceptance spec for Story 2: visibility based on Enrollment."""

    def test_only_enrolled_students_can_start_essay_attempt(self):
        """
        Desired behaviour:
        - Student *not* enrolled in course cannot start essay attempt.
        - Once enrolled, student can start attempt successfully.
        """
        _fresh_db()
        from app.database import engine
        from app.models import Course, Student, User, Exam
        from app.routers.essay_ui import start_submit

        with Session(engine) as session:
            course = Course(code=_unique_code("VIS"), name="Visibility", description=None)
            session.add(course)
            session.commit()
            session.refresh(course)

            exam = Exam(
                title="VTest",
                subject="GEN",
                duration_minutes=30,
                course_id=course.id,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow() + timedelta(minutes=30),
            )
            session.add(exam)
            session.commit()
            session.refresh(exam)
            exam_id = exam.id

            # student not enrolled
            s = Student(
                name="Not Enrolled",
                email=f"ne+{uuid.uuid4().hex[:6]}@example.com",
                matric_no=f"NE{uuid.uuid4().hex[:4]}",
            )
            session.add(s)
            session.commit()
            session.refresh(s)

            u = User(
                name="StudUser",
                email=f"stud+{uuid.uuid4().hex[:6]}@example.com",
                password_hash="x",
                role="student",
                student_id=s.id,
            )
            session.add(u)
            session.commit()
            session.refresh(u)

            user_info = type("U", (), {})()
            user_info.id = u.id
            user_info.role = u.role
            user_info.student_id = u.student_id

        with Session(engine) as session2:
            from fastapi import HTTPException

            try:
                start_submit(exam_id, session=session2, current_user=user_info)
                assert False, "start_submit should block unenrolled students"
            except HTTPException as exc:
                assert exc.status_code == 403


