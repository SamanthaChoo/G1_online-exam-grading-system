def test_attempt_duration_default_and_timeout():
    """Verify the attempt page uses a 90-minute default when exam.duration_minutes is not set,
    and that POSTing to the timeout endpoint marks the attempt as timed_out and saves answers.
    Also verify the template exposes attempts_count when multiple attempts exist.
    """
    import sys
    from pathlib import Path
    from datetime import datetime

    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Use starlette's TestClient which is compatible with the project's dependencies
    from app.database import create_db_and_tables, engine
    from sqlmodel import Session
    from app.models import Exam, Student, ExamQuestion, ExamAttempt, EssayAnswer

    # Ensure DB is created
    create_db_and_tables()

    # Create records: exam with no duration, student, question, a previous final attempt, and a current in-progress attempt
    with Session(engine) as session:
        # Use 0 to represent "unset" in the DB model (duration_minutes is NOT NULL),
        # the template/JS should treat 0 as falsy and default to 90.
        exam = Exam(title="AutoTest Exam", subject="GEN", duration_minutes=0)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        student = Student(name="Stu A", email=f"stu-{datetime.utcnow().timestamp()}@example.com", matric_no=f"M{datetime.utcnow().timestamp()}")
        session.add(student)
        session.commit()
        session.refresh(student)

        q = ExamQuestion(exam_id=exam.id, question_text="What is testing?", max_marks=10)
        session.add(q)
        session.commit()
        session.refresh(q)

        # previous final attempt
        prev = ExamAttempt(exam_id=exam.id, student_id=student.id, started_at=datetime.utcnow(), status="submitted", is_final=1)
        session.add(prev)
        session.commit()
        session.refresh(prev)

        # current in-progress attempt
        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id, started_at=datetime.utcnow(), status="in_progress", is_final=0)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        # Convert ORM objects to plain dicts while still attached to session
        exam_data = {k: getattr(exam, k) for k in ('id', 'title', 'duration_minutes')}
        attempt_data = {k: getattr(attempt, k) for k in ('id', 'exam_id', 'student_id', 'started_at', 'status')}
        q_data = {k: getattr(q, k) for k in ('id', 'question_text', 'max_marks', 'exam_id')}

    # Render the template using the same filesystem templates to inspect rendered JS
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    repo_root = Path(__file__).resolve().parent.parent
    templates_dir = repo_root / "app" / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape(["html", "xml"]))
    tmpl = env.get_template("essay/attempt.html")
    # Build minimal context for rendering (templates expect current_user/request but they can be None)
    rendered = tmpl.render(
        exam=exam_data,
        attempt=attempt_data,
        questions=[q_data],
        answers_map={},
        attempts_count=2,
        current_user=None,
        request=None,
    )

    assert "const durationMinutes = 90" in rendered
    assert "const attemptsCount = 2" in rendered

    # Now simulate the auto-submit by calling the router function directly (async)
    from app.routers.essay_ui import attempt_timeout
    import asyncio

    payload = {"answers": [{"question_id": q.id, "answer_text": "My answer"}]}

    class DummyReq:
        def __init__(self, data):
            self._data = data

        async def json(self):
            return self._data

    # Call the async endpoint function directly; pass the session explicitly
    with Session(engine) as session:
        # run the coroutine
        coro = attempt_timeout(exam.id, attempt.id, session, DummyReq(payload))
        res = asyncio.get_event_loop().run_until_complete(coro)

    # Verify attempt updated in DB
    with Session(engine) as session:
        a = session.get(ExamAttempt, attempt.id)
        assert a is not None
        assert a.status == "timed_out"
        from sqlmodel import select
        ans = session.exec(select(EssayAnswer).where(EssayAnswer.attempt_id == attempt.id)).first()
        assert ans is not None

