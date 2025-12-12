import sys
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, text


def _ensure_app_on_path():
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


_ensure_app_on_path()

# ============================================================================
# IN-MEMORY DATABASE FOR TESTING
# ============================================================================

from datetime import datetime, timedelta
import httpx
import asyncio

from app.models import (
    Student,
    User,
    Course,
    Exam,
    ExamQuestion,
    EssayAnswer,
    ExamAttempt,
    Enrollment,
    CourseLecturer,
    MCQQuestion,
    MCQResult,
)
from app.auth_utils import hash_password

# Create in-memory SQLite engine for testing
# Use sqlite:///:memory: with poolclass=StaticPool to share the same in-memory DB across threads
from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # CRITICAL: Ensures all connections share the same in-memory database
)

@pytest.fixture(scope="session")
def engine():
    """Provide test engine as a fixture."""
    return test_engine

@pytest.fixture(scope="function")
def test_engine_fixture():
    """Provide test engine for individual tests."""
    return test_engine

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables in the test database once per session."""
    SQLModel.metadata.create_all(test_engine)
    yield
    # Cleanup after all tests
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(autouse=True)
def cleanup_db_between_tests():
    """Clean up test data after each test."""
    yield  # run the test
    
    # Clean up in FK-safe order
    with Session(test_engine) as session:
        session.exec(text("DELETE FROM mcqanswer"))
        session.exec(text("DELETE FROM mcqresult"))
        session.exec(text("DELETE FROM mcqquestion"))
        session.exec(text("DELETE FROM essayanswer"))
        session.exec(text("DELETE FROM examattempt"))
        session.exec(text("DELETE FROM examquestion"))
        session.exec(text("DELETE FROM exam"))
        session.exec(text("DELETE FROM enrollment"))
        session.exec(text("DELETE FROM courselecturer"))
        session.exec(text("DELETE FROM course"))
        session.exec(text("DELETE FROM student"))
        session.exec(text("DELETE FROM user"))
        session.exec(text("DELETE FROM passwordresettoken"))
        session.commit()


# ============================================================================
# FASTAPI APP & TEST CLIENT
# ============================================================================

from app.main import app
from app.database import get_session

@pytest.fixture
def client():
    """Create test client using httpx AsyncClient with sync wrapper."""
    def override_get_session():
        # CRITICAL: Must use same test_engine instance that has tables
        with Session(test_engine) as session:
            yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    # Create event loop for this test
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Create AsyncClient
    transport = httpx.ASGITransport(app=app)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    
    # Create a sync wrapper
    class SyncClientWrapper:
        def __init__(self, async_client, loop):
            self.async_client = async_client
            self.loop = loop
        
        def get(self, *args, **kwargs):
            return self.loop.run_until_complete(self.async_client.get(*args, **kwargs))
        
        def post(self, *args, **kwargs):
            return self.loop.run_until_complete(self.async_client.post(*args, **kwargs))
        
        def put(self, *args, **kwargs):
            return self.loop.run_until_complete(self.async_client.put(*args, **kwargs))
        
        def delete(self, *args, **kwargs):
            return self.loop.run_until_complete(self.async_client.delete(*args, **kwargs))
        
        def patch(self, *args, **kwargs):
            return self.loop.run_until_complete(self.async_client.patch(*args, **kwargs))
        
        def head(self, *args, **kwargs):
            return self.loop.run_until_complete(self.async_client.head(*args, **kwargs))
        
        def options(self, *args, **kwargs):
            return self.loop.run_until_complete(self.async_client.options(*args, **kwargs))
    
    sync_client = SyncClientWrapper(async_client, loop)
    
    yield sync_client
    
    # Cleanup
    loop.run_until_complete(async_client.aclose())
    app.dependency_overrides.clear()


@pytest.fixture
def session():
    """Provide a database session for tests."""
    with Session(test_engine) as session:
        yield session
# ============================================================================
# ENTITY FIXTURES
# ============================================================================

@pytest.fixture
def admin_user():
    """Create a sample admin user."""
    with Session(test_engine) as session:
        admin = User(
            name="Admin User",
            email="admin@example.com",
            password_hash=hash_password("admin123"),
            role="admin",
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        admin_id = admin.id
    
    with Session(test_engine) as session:
        return session.get(User, admin_id)


@pytest.fixture
def lecturer_user():
    """Create a sample lecturer user."""
    with Session(test_engine) as session:
        lecturer = User(
            name="Dr. John Lecturer",
            email="lecturer@example.com",
            password_hash=hash_password("lecturer123"),
            role="lecturer",
            title="Dr.",
            staff_id="L001",
        )
        session.add(lecturer)
        session.commit()
        session.refresh(lecturer)
        lecturer_id = lecturer.id
    
    with Session(test_engine) as session:
        return session.get(User, lecturer_id)


@pytest.fixture
def student_user():
    """Create a sample student user with linked User account."""
    with Session(test_engine) as session:
        # Create User first
        user = User(
            name="Alice Student",
            email="alice@example.com",
            password_hash=hash_password("testpass123"),
            role="student",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id
        
        # Create Student linked to User
        student = Student(
            name="Alice Student",
            email="alice@example.com",
            matric_no="SWE2001",
            user_id=user_id,
        )
        session.add(student)
        session.commit()
        session.refresh(student)
        student_id = student.id
    
    with Session(test_engine) as session:
        return session.get(Student, student_id)


@pytest.fixture
def course(lecturer_user):
    """Create a sample course and assign lecturer."""
    with Session(test_engine) as session:
        course = Course(
            code="SWE101",
            name="Introduction to Software Engineering",
            description="Learn the basics of software engineering",
        )
        session.add(course)
        session.commit()
        session.refresh(course)
        course_id = course.id

        # Assign lecturer to course
        course_lecturer = CourseLecturer(
            course_id=course_id,
            lecturer_id=lecturer_user.id,
        )
        session.add(course_lecturer)
        session.commit()
    
    # Fetch fresh from DB after session close
    with Session(test_engine) as session:
        return session.get(Course, course_id)


@pytest.fixture
def enrolled_student(student_user, course):
    """Enroll a student in a course."""
    with Session(test_engine) as session:
        enrollment = Enrollment(
            course_id=course.id,
            student_id=student_user.id,
        )
        session.add(enrollment)
        session.commit()
    
    with Session(test_engine) as session:
        return session.get(Student, student_user.id)


@pytest.fixture
def essay_exam(course):
    """Create a sample essay exam."""
    with Session(test_engine) as session:
        exam = Exam(
            title="Essay Midterm",
            subject="Software Design Principles",
            duration_minutes=90,
            course_id=course.id,
            status="completed",
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow() + timedelta(minutes=30),
        )
        session.add(exam)
        session.commit()
        session.refresh(exam)
        exam_id = exam.id

        # Add essay questions
        for i in range(2):
            question = ExamQuestion(
                exam_id=exam_id,
                question_text=f"Essay Question {i+1}: Explain your understanding?",
                max_marks=10,
            )
            session.add(question)
        session.commit()
    
    with Session(test_engine) as session:
        return session.get(Exam, exam_id)


@pytest.fixture
def mcq_exam(course):
    """Create a sample MCQ exam."""
    with Session(test_engine) as session:
        exam = Exam(
            title="MCQ Quiz",
            subject="Python Basics",
            duration_minutes=30,
            course_id=course.id,
            status="completed",
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow() + timedelta(minutes=30),
        )
        session.add(exam)
        session.commit()
        session.refresh(exam)
        exam_id = exam.id

        # Add MCQ questions
        for i in range(3):
            question = MCQQuestion(
                exam_id=exam_id,
                question_text=f"MCQ Question {i+1}?",
                option_a="Option A",
                option_b="Option B",
                option_c="Option C",
                option_d="Option D",
                correct_option="A",
            )
            session.add(question)
        session.commit()
    
    with Session(test_engine) as session:
        return session.get(Exam, exam_id)


@pytest.fixture
def graded_essay_attempt(essay_exam, enrolled_student):
    """Create a graded essay attempt."""
    with Session(test_engine) as session:
        attempt = ExamAttempt(
            exam_id=essay_exam.id,
            student_id=enrolled_student.id,
            started_at=datetime.utcnow() - timedelta(minutes=30),
            submitted_at=datetime.utcnow() - timedelta(minutes=5),
            status="submitted",
        )
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
        attempt_id = attempt.id

        # Add graded answers
        from sqlmodel import select
        questions = session.exec(select(ExamQuestion).where(ExamQuestion.exam_id == essay_exam.id)).all()
        for i, question in enumerate(questions):
            answer = EssayAnswer(
                attempt_id=attempt_id,
                question_id=question.id,
                answer_text=f"Student's answer to question {i+1}.",
                marks_awarded=8.5,
                grader_feedback="Good response, but could be more detailed.",
            )
            session.add(answer)
        session.commit()
    
    with Session(test_engine) as session:
        return session.get(ExamAttempt, attempt_id)


@pytest.fixture
def ungraded_essay_attempt(essay_exam, enrolled_student):
    """Create an ungraded essay attempt."""
    with Session(test_engine) as session:
        attempt = ExamAttempt(
            exam_id=essay_exam.id,
            student_id=enrolled_student.id,
            started_at=datetime.utcnow() - timedelta(minutes=60),
            submitted_at=datetime.utcnow() - timedelta(minutes=30),
            status="submitted",
        )
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
        attempt_id = attempt.id

        # Add ungraded answers
        from sqlmodel import select
        questions = session.exec(select(ExamQuestion).where(ExamQuestion.exam_id == essay_exam.id)).all()
        for i, question in enumerate(questions):
            answer = EssayAnswer(
                attempt_id=attempt_id,
                question_id=question.id,
                answer_text=f"Ungraded student answer to question {i+1}.",
                marks_awarded=None,
                grader_feedback=None,
            )
            session.add(answer)
        session.commit()
    
    with Session(test_engine) as session:
        return session.get(ExamAttempt, attempt_id)


@pytest.fixture
def mcq_result(mcq_exam, enrolled_student):
    """Create a sample MCQ result."""
    with Session(test_engine) as session:
        result = MCQResult(
            student_id=enrolled_student.id,
            exam_id=mcq_exam.id,
            score=24,
            total_questions=3,
            graded_at=datetime.utcnow(),
        )
        session.add(result)
        session.commit()
        session.refresh(result)
        result_id = result.id
    
    with Session(test_engine) as session:
        return session.get(MCQResult, result_id)


@pytest.fixture
def student_user_no_grades():
    """Create a student user with no grade records."""
    with Session(test_engine) as session:
        # Create User first
        user = User(
            name="Bob NoGrades",
            email="bob@example.com",
            password_hash=hash_password("testpass123"),
            role="student",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id
        
        # Create Student linked to User
        student = Student(
            name="Bob NoGrades",
            email="bob@example.com",
            matric_no="SWE2002",
            user_id=user_id,
        )
        session.add(student)
        session.commit()
        session.refresh(student)
        student_id = student.id
    
    with Session(test_engine) as session:
        return session.get(Student, student_id)


@pytest.fixture
def enrolled_student_no_grades(student_user_no_grades, course):
    """Enroll a student with no grades in a course."""
    with Session(test_engine) as session:
        enrollment = Enrollment(
            course_id=course.id,
            student_id=student_user_no_grades.id,
        )
        session.add(enrollment)
        session.commit()
    
    with Session(test_engine) as session:
        return session.get(Student, student_user_no_grades.id)


# ============================================================================
# PYTEST HOOKS FOR TEST SUMMARY
# ============================================================================

test_results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "errors": 0,
}


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test result outcomes."""
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call":
        test_results["total"] += 1
        if rep.passed:
            test_results["passed"] += 1
        elif rep.failed:
            test_results["failed"] += 1
        elif rep.error:
            test_results["errors"] += 1


def pytest_sessionfinish(session, exitstatus):
    """Print test summary at the end of the session."""
    print("\n")
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    total = test_results["total"]
    passed = test_results["passed"]
    failed = test_results["failed"]
    errors = test_results["errors"]
    
    print(f"Total Tests:  {total}")
    print(f"Passed:       {passed} / {total}")
    print(f"Failed:       {failed}")
    print(f"Errors:       {errors}")
    print("=" * 70)
    print()
