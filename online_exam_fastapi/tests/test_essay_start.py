import importlib
import sys
from pathlib import Path

from sqlmodel import Session, select


def _import_app():
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    mod = importlib.import_module("app.main")
    return mod.app


def test_non_student_cannot_start():
    app = _import_app()
    # create sample exam and users
    from app.database import engine, create_db_and_tables
    from app.models import User, Student, Exam, ExamAttempt
    from sqlmodel import Session

    # ensure tables exist
    create_db_and_tables()

    import uuid

    with Session(engine) as session:
        exam = Exam(title="T1", subject="GEN", duration_minutes=10)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        exam_id = exam.id

        # create a non-student user
        u_db = User(name="Admin", email=f"a+{uuid.uuid4().hex[:8]}@example.com", password_hash="x", role="admin")
        session.add(u_db)
        session.commit()
        session.refresh(u_db)
        user_info = type("U", (), {})()
        user_info.id = u_db.id
        user_info.role = u_db.role
        user_info.student_id = u_db.student_id

    # call the router function directly to avoid TestClient/httpx compatibility issues
    from app.routers.essay_ui import start_submit

    with Session(engine) as session2:
        resp = start_submit(exam_id, session=session2, current_user=user_info)
        assert getattr(resp, "status_code", None) == 303
        assert f"/essay/{exam_id}/start" in resp.headers.get("location", "")


def test_student_can_start():
    app = _import_app()
    from app.database import engine, create_db_and_tables
    from app.models import User, Student, Exam, ExamAttempt
    from app.services.essay_service import create_exam

    # ensure tables exist
    create_db_and_tables()

    import uuid

    with Session(engine) as session:
        # ensure a student exists
        s = Student(name="Test Stud", email=f"s+{uuid.uuid4().hex[:8]}@example.com", matric_no=f"S{uuid.uuid4().hex[:4]}")
        session.add(s)
        session.commit()
        session.refresh(s)
        s_id = s.id

        # create student user linked to student
        u_db = User(name="StudUser", email=f"suser+{uuid.uuid4().hex[:8]}@example.com", password_hash="x", role="student", student_id=s.id)
        session.add(u_db)
        session.commit()
        session.refresh(u_db)

        # create an exam
        exam = Exam(title="T2", subject="GEN", duration_minutes=5)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        exam_id = exam.id

        user_info = type("U", (), {})()
        user_info.id = u_db.id
        user_info.role = u_db.role
        user_info.student_id = u_db.student_id

    from app.routers.essay_ui import start_submit

    with Session(engine) as session2:
        resp = start_submit(exam_id, session=session2, current_user=user_info)
        assert getattr(resp, "status_code", None) == 303
        loc = resp.headers.get("location", "")
        assert f"/essay/{exam_id}/attempt/" in loc

    # verify attempt created
    from app.database import engine as _engine
    with Session(_engine) as session:
        stmt = select(ExamAttempt).where(ExamAttempt.exam_id == exam_id).where(ExamAttempt.student_id == s_id)
        attempt = session.exec(stmt).first()
        assert attempt is not None

    # no dependency overrides used in this test
