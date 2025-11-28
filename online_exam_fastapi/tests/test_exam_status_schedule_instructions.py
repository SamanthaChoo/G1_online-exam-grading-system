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


class TestExamStatusField:
    """Acceptance tests for status field behaviour."""

    def test_status_validation_and_default(self):
        """Pass status must be valid and default is 'draft'."""
        _fresh_db()
        from app.database import engine
        from app.routers.exams import create_exam
        from app.models import Course, Exam

        with Session(engine) as session:
            course = Course(
                code=f"EX05-{uuid.uuid4().hex[:6]}", name="ExamCourse5", description=None
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            # invalid status
            resp = asyncio.run(create_exam(
                request=_DummyRequest(),
                title="T",
                subject="S",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(30),
                instructions=None,
                status="weird",
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400
            assert "status" in resp.context["errors"]

            # valid draft
            resp2 = asyncio.run(create_exam(
                request=None,
                title="T2",
                subject="S2",
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
            exam = session.exec(select(Exam).where(Exam.title == "T2")).first()
            assert exam.status == "draft"

    def test_cannot_jump_to_completed_without_schedule(self):
        """Desired: cannot mark completed without valid start/end schedule."""
        _fresh_db()
        from app.database import engine
        from app.routers.exams import create_exam
        from app.models import Course

        with Session(engine) as session:
            course = Course(
                code=f"EX06-{uuid.uuid4().hex[:6]}", name="ExamCourse6", description=None
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            resp = asyncio.run(create_exam(
                request=_DummyRequest(),
                title="T",
                subject="S",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=None,
                end_time=None,
                instructions=None,
                status="completed",
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400


class TestExamSchedulingDefaults:
    """Acceptance tests for start_time/end_time."""

    def test_schedule_required_and_end_after_start(self):
        """Pass schedule fields required and end must be after start."""
        _fresh_db()
        from app.database import engine
        from app.routers.exams import create_exam
        from app.models import Course

        with Session(engine) as session:
            course = Course(
                code=f"EX07-{uuid.uuid4().hex[:6]}", name="ExamCourse7", description=None
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            # missing start
            resp = asyncio.run(create_exam(
                request=_DummyRequest(),
                title="T",
                subject="S",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=None,
                end_time=_now_plus_minutes_iso(30),
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400
            assert "start_time" in resp.context["errors"]

            # end before start
            start = _now_plus_minutes_iso(60)
            end = _now_plus_minutes_iso(30)
            resp2 = asyncio.run(create_exam(
                request=_DummyRequest(),
                title="T",
                subject="S",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=start,
                end_time=end,
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 400
            assert "end_time" in resp2.context["errors"]

    def test_schedule_canonical_timezone_and_preserved_on_edit(self):
        """Desired: datetimes stored in canonical TZ and preserved if not changed on edit."""
        _fresh_db()
        from app.database import engine
        from app.routers.exams import create_exam, update_exam
        from app.models import Course, Exam

        with Session(engine) as session:
            course = Course(
                code=f"EX08-{uuid.uuid4().hex[:6]}", name="ExamCourse8", description=None
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            start_iso = _now_iso()
            end_iso = _now_plus_minutes_iso(30)
            title_initial = f"T-{uuid.uuid4().hex[:6]}"
            title_updated = f"T2-{uuid.uuid4().hex[:6]}"
            resp = asyncio.run(create_exam(
                request=None,
                title=title_initial,
                subject="S",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=start_iso,
                end_time=end_iso,
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 303
            exam = session.exec(
                select(Exam)
                .where(Exam.course_id == course.id, Exam.title == title_initial)
                .order_by(Exam.id.desc())
            ).first()
            orig_start = exam.start_time
            orig_end = exam.end_time

            resp2 = asyncio.run(update_exam(
                exam_id=exam.id,
                request=None,
                title=title_updated,
                subject="S2",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=start_iso,
                end_time=end_iso,
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 303
            session.refresh(exam)
            assert exam.start_time == orig_start
            assert exam.end_time == orig_end


class TestExamInstructionsField:
    """Acceptance tests for instructions field."""

    def test_instructions_trim_and_html_escaped(self):
        """
        Desired:
        - Leading/trailing spaces are stripped.
        - Instructions render with HTML-escaping in the template.
        """
        _fresh_db()
        from app.database import engine
        from app.routers.exams import create_exam
        from app.models import Course, Exam
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        with Session(engine) as session:
            course = Course(
                code=f"EX09-{uuid.uuid4().hex[:6]}", name="ExamCourse9", description=None
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            instr = "   <script>alert('x')</script>   "
            title_value = f"T-{uuid.uuid4().hex[:6]}"
            resp = asyncio.run(create_exam(
                request=None,
                title=title_value,
                subject="S",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(30),
                instructions=instr,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 303
            exam = session.exec(
                select(Exam)
                .where(Exam.course_id == course.id, Exam.title == title_value)
                .order_by(Exam.id.desc())
            ).first()
            assert exam.instructions == "<script>alert('x')</script>"

            # render detail template
            repo_root = Path(__file__).resolve().parent.parent
            templates_dir = repo_root / "app" / "templates"
            env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                autoescape=select_autoescape(["html", "xml"]),
            )
            tmpl = env.get_template("exams/detail.html")
            rendered = tmpl.render(
                request=None,
                exam=exam,
                course=None,
                current_user=None,
            )
            assert "&lt;script&gt;" in rendered

    def test_instructions_character_limit(self):
        """Desired: reject instructions that exceed the maximum character limit."""
        _fresh_db()
        from app.database import engine
        from app.routers.exams import create_exam, EXAM_INSTRUCTIONS_MAX_LENGTH
        from app.models import Course

        with Session(engine) as session:
            course = Course(
                code=f"EX10-{uuid.uuid4().hex[:6]}", name="ExamCourse10", description=None
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            # Instructions exceeding max length (2000 characters)
            long_instructions = "A" * (EXAM_INSTRUCTIONS_MAX_LENGTH + 1)
            title_value = f"T-{uuid.uuid4().hex[:6]}"
            resp = asyncio.run(create_exam(
                request=_DummyRequest(),
                title=title_value,
                subject="S",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(30),
                instructions=long_instructions,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400
            assert "instructions" in resp.context["errors"]
            assert str(EXAM_INSTRUCTIONS_MAX_LENGTH) in resp.context["errors"]["instructions"]

            # Instructions at max length (2000 characters) should be accepted
            max_instructions = "A" * EXAM_INSTRUCTIONS_MAX_LENGTH
            title_value2 = f"T2-{uuid.uuid4().hex[:6]}"
            resp2 = asyncio.run(create_exam(
                request=None,
                title=title_value2,
                subject="S",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=_now_iso(),
                end_time=_now_plus_minutes_iso(30),
                instructions=max_instructions,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 303


class TestExamStartTimeValidation:
    """Acceptance tests for start time validation (not before today)."""

    def test_start_time_cannot_be_in_past(self):
        """Desired: reject exam start time that is in the past."""
        _fresh_db()
        from app.database import engine
        from app.routers.exams import create_exam
        from app.models import Course

        with Session(engine) as session:
            course = Course(
                code=f"EX11-{uuid.uuid4().hex[:6]}", name="ExamCourse11", description=None
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            # Start time in the past (yesterday)
            from datetime import timedelta
            past_time = (datetime.now(timezone.utc) - timedelta(days=1)).replace(microsecond=0).isoformat()
            future_end_time = _now_plus_minutes_iso(60)

            resp = asyncio.run(create_exam(
                request=_DummyRequest(),
                title="Past Exam",
                subject="S",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=past_time,
                end_time=future_end_time,
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400
            assert "start_time" in resp.context["errors"]
            assert "past" in resp.context["errors"]["start_time"].lower()

            # Start time in the future should be accepted
            future_start_time = _now_plus_minutes_iso(60)
            future_end_time2 = _now_plus_minutes_iso(120)
            title_value = f"T-{uuid.uuid4().hex[:6]}"
            resp2 = asyncio.run(create_exam(
                request=None,
                title=title_value,
                subject="S",
                duration_minutes="30",
                course_id=str(course.id),
                start_time=future_start_time,
                end_time=future_end_time2,
                instructions=None,
                status="draft",
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 303


