import sys
from pathlib import Path
from datetime import datetime
import asyncio

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
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


class TestCourseLecturerAssignment:
    """Acceptance tests for assigning lecturers to courses."""

    def test_assign_and_update_lecturers(self):
        """Pass can assign multiple lecturers and update them on edit."""
        _fresh_db()
        from app.database import engine
        from app.models import User, CourseLecturer, Course
        from app.routers.courses import create_course, update_course

        with Session(engine) as session:
            # create two lecturers
            l1 = User(
                name="L1",
                email=f"l1+{uuid.uuid4().hex[:6]}@example.com",
                password_hash="x",
                role="lecturer",
            )
            l2 = User(
                name="L2",
                email=f"l2+{uuid.uuid4().hex[:6]}@example.com",
                password_hash="x",
                role="lecturer",
            )
            session.add(l1)
            session.add(l2)
            session.commit()
            session.refresh(l1)
            session.refresh(l2)

            acting = type("U", (), {})()
            acting.id = l1.id
            acting.role = "lecturer"

            # create course with both lecturers
            # Create a mock request with form data for tests
            class MockForm:
                def __init__(self, lecturer_ids_list):
                    self._lecturer_ids = [str(lid) for lid in lecturer_ids_list]
                def getlist(self, key):
                    if key == "lecturer_ids":
                        return self._lecturer_ids
                    return []
            
            class MockRequest:
                async def form(self):
                    return MockForm([l1.id, l2.id])
            
            import asyncio
            resp = asyncio.run(create_course(
                request=MockRequest(),
                code=_unique_code("LECASSIGN01"),
                name="Assign Test",
                description=None,
                session=session,
                current_user=acting,
            ))
            assert getattr(resp, "status_code", None) == 303
            course = session.exec(select(Course).order_by(Course.id.desc())).first()
            cls = session.exec(
                select(CourseLecturer).where(CourseLecturer.course_id == course.id)
            ).all()
            assert {c.lecturer_id for c in cls} == {l1.id, l2.id}

            # update: keep only l2
            class MockForm2:
                def __init__(self, lecturer_ids_list):
                    self._lecturer_ids = [str(lid) for lid in lecturer_ids_list]
                def getlist(self, key):
                    if key == "lecturer_ids":
                        return self._lecturer_ids
                    return []
            
            class MockRequest2:
                async def form(self):
                    return MockForm2([l2.id])
            
            import asyncio
            resp2 = asyncio.run(update_course(
                course_id=course.id,
                request=MockRequest2(),
                code=course.code,
                name=course.name,
                description=course.description,
                session=session,
                current_user=acting,
            ))
            assert getattr(resp2, "status_code", None) == 303
            cls2 = session.exec(
                select(CourseLecturer).where(CourseLecturer.course_id == course.id)
            ).all()
            assert {c.lecturer_id for c in cls2} == {l2.id}


class TestCourseEnrollment:
    """Acceptance tests for Enrollment table and enrol/unenrol behaviour."""

    def test_enrollment_add_remove_and_meta(self):
        """Pass add/remove students and ensure enrolled_at is populated."""
        _fresh_db()
        from app.database import engine
        from app.models import Course, Student, Enrollment
        from app.routers.courses import enroll_students

        with Session(engine) as session:
            course = Course(code=_unique_code("ENR01"), name="Enroll", description=None)
            s1 = Student(
                name="S1",
                email=f"s1+{uuid.uuid4().hex[:6]}@example.com",
                matric_no=f"M{uuid.uuid4().hex[:4]}",
            )
            s2 = Student(
                name="S2",
                email=f"s2+{uuid.uuid4().hex[:6]}@example.com",
                matric_no=f"M{uuid.uuid4().hex[:4]}",
            )
            session.add(course)
            session.add(s1)
            session.add(s2)
            session.commit()
            session.refresh(course)
            session.refresh(s1)
            session.refresh(s2)

            lecturer = type("U", (), {})()
            lecturer.id = 1
            lecturer.role = "lecturer"

            # enroll both
            # Create a mock request with form data for tests
            class MockForm:
                def __init__(self, student_ids_list):
                    self._student_ids = [str(sid) for sid in student_ids_list]
                def getlist(self, key):
                    if key == "student_ids":
                        return self._student_ids
                    return []
            
            class MockRequest:
                async def form(self):
                    return MockForm([s1.id, s2.id])
            
            resp = asyncio.run(enroll_students(
                course_id=course.id,
                request=MockRequest(),
                session=session,
                current_user=lecturer,
            ))
            assert getattr(resp, "status_code", None) == 303
            ens = session.exec(
                select(Enrollment).where(Enrollment.course_id == course.id)
            ).all()
            assert {e.student_id for e in ens} == {s1.id, s2.id}
            for e in ens:
                assert isinstance(e.enrolled_at, datetime)

            # now remove s1
            class MockRequest2:
                async def form(self):
                    return MockForm([s2.id])
            
            resp2 = asyncio.run(enroll_students(
                course_id=course.id,
                request=MockRequest2(),
                session=session,
                current_user=lecturer,
            ))
            assert getattr(resp2, "status_code", None) == 303
            ens2 = session.exec(
                select(Enrollment).where(Enrollment.course_id == course.id)
            ).all()
            assert {e.student_id for e in ens2} == {s2.id}


