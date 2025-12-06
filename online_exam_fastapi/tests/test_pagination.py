import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

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


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _now_plus_minutes_iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).replace(
        microsecond=0
    ).isoformat()


@pytest.mark.usefixtures("cleanup_db_between_tests")
class TestCourseListPagination:
    """Acceptance tests for course list pagination."""

    def test_course_list_pagination_with_many_courses(self):
        """Pass: course list paginates correctly when there are more than 10 courses."""
        _fresh_db()
        from app.database import engine
        from app.routers.courses import list_courses
        from app.models import Course

        with Session(engine) as session:
            # Count existing courses
            existing_count = len(session.exec(select(Course)).all())
            
            # Create 15 courses
            created_codes = []
            for i in range(15):
                code = _unique_code(f"PAG{i:02d}")
                created_codes.append(code)
                course = Course(
                    code=code,
                    name=f"Pagination Test Course {i}",
                    description=None,
                )
                session.add(course)
            session.commit()

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            # Test page 1
            class MockRequest:
                pass

            resp1 = list_courses(
                request=MockRequest(),
                sort="created",
                direction="desc",
                page=1,
                session=session,
                current_user=user,
            )
            assert getattr(resp1, "status_code", None) == 200
            assert len(resp1.context["courses"]) == 10
            assert resp1.context["current_page"] == 1
            total_items = resp1.context["total_items"]
            total_pages = resp1.context["total_pages"]
            assert total_items >= 15  # At least our 15 courses
            assert total_pages >= 2  # At least 2 pages
            assert resp1.context["items_per_page"] == 10

            # Test page 2
            resp2 = list_courses(
                request=MockRequest(),
                sort="created",
                direction="desc",
                page=2,
                session=session,
                current_user=user,
            )
            assert getattr(resp2, "status_code", None) == 200
            assert resp2.context["current_page"] == 2
            assert resp2.context["total_pages"] == total_pages
            # Should have some courses on page 2 (at least 5 from our 15)
            assert len(resp2.context["courses"]) > 0

            # Test page beyond total (should show last page)
            resp3 = list_courses(
                request=MockRequest(),
                sort="created",
                direction="desc",
                page=999,
                session=session,
                current_user=user,
            )
            assert resp3.context["current_page"] == total_pages  # Clamped to last page
            assert len(resp3.context["courses"]) > 0

    def test_course_list_pagination_with_few_courses(self):
        """Pass: course list shows all courses when there are 10 or fewer."""
        _fresh_db()
        from app.database import engine
        from app.routers.courses import list_courses
        from app.models import Course

        with Session(engine) as session:
            # Create 5 courses
            for i in range(5):
                course = Course(
                    code=_unique_code(f"FEW{i:02d}"),
                    name=f"Few Courses Test {i}",
                    description=None,
                )
                session.add(course)
            session.commit()

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            class MockRequest:
                pass

            resp = list_courses(
                request=MockRequest(),
                sort="created",
                direction="desc",
                page=1,
                session=session,
                current_user=user,
            )
            assert getattr(resp, "status_code", None) == 200
            assert len(resp.context["courses"]) == 5
            assert resp.context["current_page"] == 1
            assert resp.context["total_pages"] == 1
            assert resp.context["total_items"] == 5


@pytest.mark.usefixtures("cleanup_db_between_tests")
class TestExamListPagination:
    """Acceptance tests for exam list pagination."""

    def test_exam_list_pagination_with_many_exams(self):
        """Pass: exam list paginates correctly when there are more than 10 exams."""
        _fresh_db()
        from app.database import engine
        from app.routers.exams import exams_for_course
        from app.models import Course, Exam

        with Session(engine) as session:
            # Create a course
            course = Course(
                code=_unique_code("EXAMPAG"),
                name="Exam Pagination Test",
                description=None,
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            # Create 15 exams for this course
            for i in range(15):
                exam = Exam(
                    title=f"Exam {i}",
                    subject=f"Subject {i}",
                    duration_minutes=60,
                    course_id=course.id,
                    start_time=datetime.utcnow() + timedelta(days=i),
                    end_time=datetime.utcnow() + timedelta(days=i, hours=1),
                    status="draft",
                )
                session.add(exam)
            session.commit()

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            class MockRequest:
                pass

            # Test page 1
            resp1 = exams_for_course(
                course_id=course.id,
                request=MockRequest(),
                sort="start",
                direction="asc",
                page=1,
                session=session,
                current_user=user,
            )
            assert getattr(resp1, "status_code", None) == 200
            assert len(resp1.context["exams"]) == 10
            assert resp1.context["current_page"] == 1
            assert resp1.context["total_pages"] == 2
            assert resp1.context["total_items"] == 15

            # Test page 2
            resp2 = exams_for_course(
                course_id=course.id,
                request=MockRequest(),
                sort="start",
                direction="asc",
                page=2,
                session=session,
                current_user=user,
            )
            assert getattr(resp2, "status_code", None) == 200
            assert len(resp2.context["exams"]) == 5
            assert resp2.context["current_page"] == 2


@pytest.mark.usefixtures("cleanup_db_between_tests")
class TestStudentEnrollmentPagination:
    """Acceptance tests for student enrollment list pagination."""

    def test_student_enrollment_pagination_with_many_students(self):
        """Pass: student enrollment list paginates available students correctly."""
        _fresh_db()
        from app.database import engine
        from app.routers.courses import enroll_form
        from app.models import Course, Student, Enrollment

        with Session(engine) as session:
            # Create a course
            course = Course(
                code=_unique_code("ENRPAG"),
                name="Enrollment Pagination Test",
                description=None,
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            # Create 15 students
            students = []
            for i in range(15):
                student = Student(
                    name=f"Student {i}",
                    email=f"student{i}+{uuid.uuid4().hex[:6]}@example.com",
                    matric_no=f"M{uuid.uuid4().hex[:4]}",
                )
                session.add(student)
                students.append(student)
            session.commit()
            for s in students:
                session.refresh(s)

            # Enroll first 2 students
            session.add(Enrollment(course_id=course.id, student_id=students[0].id))
            session.add(Enrollment(course_id=course.id, student_id=students[1].id))
            session.commit()

            user = type("U", (), {})()
            user.id = 1
            user.role = "lecturer"

            class MockRequest:
                pass

            # Test page 1 - should show 2 enrolled + 10 available
            resp1 = enroll_form(
                course_id=course.id,
                request=MockRequest(),
                q=None,
                page=1,
                session=session,
                current_user=user,
            )
            assert getattr(resp1, "status_code", None) == 200
            assert len(resp1.context["enrolled_students"]) == 2  # All enrolled shown
            assert len(resp1.context["available_students"]) == 10  # Paginated
            assert resp1.context["current_page"] == 1
            assert resp1.context["total_pages"] == 2  # 13 available students, 10 per page
            assert resp1.context["total_items"] == 13  # 15 total - 2 enrolled = 13 available

            # Test page 2 - should show 2 enrolled + 3 available
            resp2 = enroll_form(
                course_id=course.id,
                request=MockRequest(),
                q=None,
                page=2,
                session=session,
                current_user=user,
            )
            assert getattr(resp2, "status_code", None) == 200
            assert len(resp2.context["enrolled_students"]) == 2  # All enrolled still shown
            assert len(resp2.context["available_students"]) == 3  # Remaining available
            assert resp2.context["current_page"] == 2

