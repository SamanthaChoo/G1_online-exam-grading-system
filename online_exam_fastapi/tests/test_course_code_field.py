import sys
from pathlib import Path
import asyncio

import pytest
from sqlmodel import Session, select
import uuid
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


class _DummyRequest:
    """Minimal stub so TemplateResponse(request=...) does not explode in tests."""

    def __init__(self):
        self.scope = {"type": "http"}


def _unique_code(prefix: str = "COURSE") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


class TestCourseCodeField:
    """Acceptance tests for Course.code."""

    def test_create_course_trim_unique_and_persist(self):
        """Pass create course with trimmed, unique code and verify persistence."""
        _fresh_db()
        from app.database import engine
        from app.models import Course
        from app.routers.courses import create_course

        # current_user is only used for role checking via dependency in real app;
        # router function itself only needs it to exist, so we can use a simple stub.
        user = type("U", (), {})()
        user.id = 1
        user.role = "lecturer"

        with Session(engine) as session:
            raw_code = _unique_code("SWE3001").lower()
            code_in = f"  {raw_code}  "
            name_in = "Software Eng"
            
            class MockForm:
                def getlist(self, key):
                    return []
            
            class MockRequest:
                async def form(self):
                    return MockForm()
            
            resp = asyncio.run(create_course(
                request=MockRequest(),
                code=code_in,
                name=name_in,
                description="desc",
                session=session,
                current_user=user,
            ))
            # Should redirect on success
            assert getattr(resp, "status_code", None) == 303

            trimmed_code = code_in.strip().upper()
            c = session.exec(select(Course).where(Course.code == trimmed_code)).first()
            assert c is not None
            assert c.name == name_in

    def test_reject_empty_code(self):
        """Pass reject empty / whitespace-only course code."""
        _fresh_db()
        from app.database import engine
        from app.routers.courses import create_course

        user = type("U", (), {})()
        user.id = 1
        user.role = "lecturer"

        with Session(engine) as session:
            class MockForm:
                def getlist(self, key):
                    return []
            
            class MockRequest:
                async def form(self):
                    return MockForm()
            
            resp = asyncio.run(create_course(
                request=MockRequest(),
                code="   ",
                name="Some name",
                description=None,
                session=session,
                current_user=user,
            ))
            # On validation error we get a TemplateResponse, not redirect
            assert getattr(resp, "status_code", None) == 400
            ctx = resp.context
            assert "code" in ctx["errors"]
            assert "required" in ctx["errors"]["code"].lower()

    def test_duplicate_code_rejected(self):
        """Pass reject duplicate code via validation before DB constraint."""
        _fresh_db()
        from app.database import engine
        from app.models import Course
        from app.routers.courses import create_course

        user = type("U", (), {})()
        user.id = 1
        user.role = "lecturer"

        with Session(engine) as session:
            base_code = _unique_code("DUP1001")
            
            class MockForm:
                def getlist(self, key):
                    return []
            
            class MockRequest:
                async def form(self):
                    return MockForm()
            
            initial_resp = asyncio.run(create_course(
                request=MockRequest(),
                code=base_code,
                name="First",
                description=None,
                session=session,
                current_user=user,
            ))
            assert getattr(initial_resp, "status_code", None) == 303

            resp = asyncio.run(create_course(
                request=MockRequest(),
                code=base_code.lower(),
                name="Second",
                description=None,
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400
            ctx = resp.context
            assert "code" in ctx["errors"]
            assert "already" in ctx["errors"]["code"].lower()

    def test_reject_overly_long_or_invalid_code(self):
        """Pass reject overly long code and code with invalid characters (spec behaviour)."""
        _fresh_db()
        from app.database import engine
        from app.routers.courses import create_course

        user = type("U", (), {})()
        user.id = 1
        user.role = "lecturer"

        with Session(engine) as session:
            class MockForm:
                def getlist(self, key):
                    return []
            
            class MockRequest:
                async def form(self):
                    return MockForm()
            
            long_code = "X" * 50  # >20 chars for acceptance spec
            resp1 = asyncio.run(create_course(
                request=MockRequest(),
                code=long_code,
                name="Name",
                description=None,
                session=session,
                current_user=user,
            ))
            assert getattr(resp1, "status_code", None) == 400

            bad_code = "BAD CODE❌"
            resp2 = asyncio.run(create_course(
                request=MockRequest(),
                code=bad_code,
                name="Name",
                description=None,
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 400


