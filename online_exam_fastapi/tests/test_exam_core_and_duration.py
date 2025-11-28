import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import asyncio

import pytest
from sqlmodel import Session, select
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


class _DummyRequest:
    def __init__(self):
        self.scope = {"type": "http"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _now_plus_minutes_iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).replace(
        microsecond=0
    ).isoformat()


class TestExamCoreFieldBoundaries:
    """Acceptance tests for title/subject basic behaviour."""

    def test_title_subject_required(self):
        """Pass title and subject are required."""
        _fresh_db()
        from app.database import engine
        from app.routers.exams import create_exam
        from app.models import Course

        with Session(engine) as session:
            course = Course(
                code=f"EX01-{uuid.uuid4().hex[:6]}", name="ExamCourse", description=None
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            # missing title
            resp = asyncio.run(create_exam(
                request=_DummyRequest(),
                title="   ",
                subject="Math",
                duration_minutes="60",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(60),
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400
            assert "title" in resp.context["errors"]

            # missing subject
            resp2 = asyncio.run(create_exam(
                request=_DummyRequest(),
                title="Final",
                subject="   ",
                duration_minutes="60",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(60),
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 400
            assert "subject" in resp2.context["errors"]

    def test_title_subject_length_and_trim(self):
        """Desired: reject overly long title/subject and trim outer spaces."""
        _fresh_db()
        from app.database import engine
        from app.routers.exams import create_exam
        from app.models import Course, Exam

        with Session(engine) as session:
            course = Course(
                code=f"EX02-{uuid.uuid4().hex[:6]}", name="ExamCourse2", description=None
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            long_title = "T" * 500
            resp = asyncio.run(create_exam(
                request=_DummyRequest(),
                title=long_title,
                subject="Subj",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(30),
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400

            resp2 = asyncio.run(create_exam(
                request=None,
                title="  Nice Title  ",
                subject="  Nice Subj ",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(30),
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 303
            exam = session.exec(select(Exam).where(Exam.subject == "Nice Subj")).first()
            assert exam.title == "Nice Title"


class TestExamDurationField:
    """Acceptance tests for duration_minutes."""

    def test_duration_basic_validation(self):
        """Pass duration must be numeric and >0."""
        _fresh_db()
        from app.database import engine
        from app.routers.exams import create_exam
        from app.models import Course

        with Session(engine) as session:
            course = Course(
                code=f"EX03-{uuid.uuid4().hex[:6]}", name="ExamCourse3", description=None
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            # non-numeric
            resp = asyncio.run(create_exam(
                request=_DummyRequest(),
                title="T",
                subject="S",
                duration_minutes="abc",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(30),
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400
            assert "duration_minutes" in resp.context["errors"]

            # zero
            resp2 = asyncio.run(create_exam(
                request=_DummyRequest(),
                title="T",
                subject="S",
                duration_minutes="0",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(30),
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 400

    def test_duration_limits(self):
        """Desired: reject duration above reasonable max and accept boundary values."""
        _fresh_db()
        from app.database import engine
        from app.routers.exams import create_exam
        from app.models import Course

        with Session(engine) as session:
            course = Course(
                code=f"EX04-{uuid.uuid4().hex[:6]}", name="ExamCourse4", description=None
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            # too long >600
            resp = asyncio.run(create_exam(
                request=_DummyRequest(),
                title="T",
                subject="S",
                duration_minutes="601",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(601),
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400

            # boundary accepted
            resp2 = asyncio.run(create_exam(
                request=None,
                title="T",
                subject="S",
                duration_minutes="600",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(600),
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 303


