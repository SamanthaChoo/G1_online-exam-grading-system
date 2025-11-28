import sys
from pathlib import Path
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


def _unique_code(prefix: str = "COURSE") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}".upper()


class _DummyRequest:
    def __init__(self):
        self.scope = {"type": "http"}


class TestCourseNameField:
    """Acceptance tests for Course.name."""

    def test_name_required(self):
        """Pass reject blank course name."""
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
                code=_unique_code("NAME1001"),
                name="   ",
                description=None,
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400
            ctx = resp.context
            assert "name" in ctx["errors"]

    def test_name_stored_as_is(self):
        """Pass name stored in DB as provided."""
        _fresh_db()
        from app.database import engine
        from app.models import Course
        from app.routers.courses import create_course

        user = type("U", (), {})()
        user.id = 1
        user.role = "lecturer"

        code_value = _unique_code("NAME1002")
        with Session(engine) as session:
            class MockForm:
                def getlist(self, key):
                    return []
            
            class MockRequest:
                async def form(self):
                    return MockForm()
            
            resp = asyncio.run(create_course(
                request=MockRequest(),
                code=code_value,
                name=" Software Engineering ",
                description=None,
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 303

        with Session(engine) as verify_session:
            c = verify_session.exec(select(Course).order_by(Course.id.desc())).first()
            assert c is not None
            assert c.code == code_value
            # Current implementation trims leading/trailing whitespace but keeps inner spaces.
            assert c.name == "Software Engineering"

    def test_name_length_and_trim_boundaries(self):
        """Desired: enforce max length and outer-trim while preserving inner spaces."""
        _fresh_db()
        from app.database import engine
        from app.routers.courses import create_course
        from app.models import Course

        user = type("U", (), {})()
        user.id = 1
        user.role = "lecturer"

        long_name = "N" * 200  # >120 as per spec suggestion
        with Session(engine) as session:
            class MockForm:
                def getlist(self, key):
                    return []
            
            class MockRequest:
                async def form(self):
                    return MockForm()
            
            resp = asyncio.run(create_course(
                request=MockRequest(),
                code=_unique_code("LONGNAME01"),
                name=long_name,
                description=None,
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400

        code_value = _unique_code("TRIMNAME01")
        with Session(engine) as session:
            class MockForm2:
                def getlist(self, key):
                    return []
            
            class MockRequest2:
                async def form(self):
                    return MockForm2()
            
            resp2 = asyncio.run(create_course(
                request=MockRequest2(),
                code=code_value,
                name="  Nice Name  ",
                description=None,
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 303

        with Session(engine) as verify_session:
            c = verify_session.exec(select(Course).order_by(Course.id.desc())).first()
            assert c.name == "Nice Name"
            assert c.code == code_value


class TestCourseDescriptionField:
    """Acceptance tests for Course.description."""

    def test_optional_and_multiline_description(self):
        """Pass description is optional; multiline text is persisted."""
        _fresh_db()
        from app.database import engine
        from app.models import Course
        from app.routers.courses import create_course

        user = type("U", (), {})()
        user.id = 1
        user.role = "lecturer"

        desc = "Line1\nLine2\nLine3"
        code_value = _unique_code("DESCMULTI01")
        # Create a mock request with form data for tests
        class MockForm:
            def __init__(self, lecturer_ids_list=None):
                self._lecturer_ids = [str(lid) for lid in (lecturer_ids_list or [])]
            def getlist(self, key):
                if key == "lecturer_ids":
                    return self._lecturer_ids
                return []
        
        class MockRequest:
            async def form(self):
                return MockForm()
        
        with Session(engine) as session:
            resp = asyncio.run(create_course(
                request=MockRequest(),
                code=code_value,
                name="Desc Test",
                description=desc,
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 303

        with Session(engine) as verify_session:
            c = verify_session.exec(select(Course).order_by(Course.id.desc())).first()
            assert c is not None
            assert c.code == code_value
            assert c.description == desc

        code_value = _unique_code("DESCNONE01")
        with Session(engine) as session:
            resp2 = asyncio.run(create_course(
                request=MockRequest(),
                code=code_value,
                name="No Desc",
                description=None,
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 303

        with Session(engine) as verify_session:
            c2 = verify_session.exec(select(Course).order_by(Course.id.desc())).first()
            assert c2.description is None
            assert c2.code == code_value

    def test_description_character_limit(self):
        """Desired: reject descriptions that exceed the maximum character limit."""
        _fresh_db()
        from app.database import engine
        from app.routers.courses import create_course, COURSE_DESCRIPTION_MAX_LENGTH
        from app.models import Course

        user = type("U", (), {})()
        user.id = 1
        user.role = "lecturer"

        # Create a mock request with form data for tests
        class MockForm:
            def __init__(self, lecturer_ids_list=None):
                self._lecturer_ids = [str(lid) for lid in (lecturer_ids_list or [])]
            def getlist(self, key):
                if key == "lecturer_ids":
                    return self._lecturer_ids
                return []
        
        class MockRequest:
            async def form(self):
                return MockForm()

        with Session(engine) as session:
            # Description exceeding max length (500 characters)
            long_description = "A" * (COURSE_DESCRIPTION_MAX_LENGTH + 1)
            code_value = _unique_code("DESCLONG01")
            resp = asyncio.run(create_course(
                request=MockRequest(),
                code=code_value,
                name="Long Desc Test",
                description=long_description,
                session=session,
                current_user=user,
            ))
            assert getattr(resp, "status_code", None) == 400
            assert "description" in resp.context["errors"]
            assert str(COURSE_DESCRIPTION_MAX_LENGTH) in resp.context["errors"]["description"]

            # Description at max length (500 characters) should be accepted
            max_description = "A" * COURSE_DESCRIPTION_MAX_LENGTH
            code_value2 = _unique_code("DESCMAX01")
            resp2 = asyncio.run(create_course(
                request=MockRequest(),
                code=code_value2,
                name="Max Desc Test",
                description=max_description,
                session=session,
                current_user=user,
            ))
            assert getattr(resp2, "status_code", None) == 303


