import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.database import engine
from app.auth_utils import hash_password
from app.models import Course, User, Exam


@pytest.fixture
def client():
    """Create a test client that doesn't follow redirects."""
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def setup_course_and_lecturer():
    """Setup a course, lecturer, and exam for testing."""
    with Session(engine) as s:
        course = Course(code="TST100", name="Test Course")
        s.add(course)
        s.commit()
        s.refresh(course)
        
        lecturer = User(
            name="Test Lecturer",
            email="lecturer@test.com",
            password_hash=hash_password("Lect1!"),
            role="lecturer",
            staff_id="L100"
        )
        s.add(lecturer)
        s.commit()
        s.refresh(lecturer)
        
        exam = Exam(
            title="Test Exam",
            subject="Testing",
            duration_minutes=60,
            course_id=course.id
        )
        s.add(exam)
        s.commit()
        s.refresh(exam)
        
        return course, lecturer, exam


@pytest.mark.usefixtures("cleanup_db")
def test_create_mcq_success(client, setup_course_and_lecturer):
    """Test successful MCQ creation."""
    course, lecturer, exam = setup_course_and_lecturer
    
    # Login as lecturer
    resp_login = client.post(
        "/auth/login",
        data={
            "login_type": "lecturer",
            "staff_id": "L100",
            "password": "Lect1!"
        }
    )
    assert resp_login.status_code == 303
    
    # Create MCQ
    resp = client.post(
        f"/exams/{exam.id}/mcq/new",
        data={
            "question_text": "What is the capital of France?",
            "option_a": "London",
            "option_b": "Paris",
            "option_c": "Berlin",
            "option_d": "Madrid",
            "correct_option": "B"
        }
    )
    assert resp.status_code == 303


@pytest.mark.usefixtures("cleanup_db")
def test_create_mcq_missing_option(client, setup_course_and_lecturer):
    """Test MCQ creation with missing option."""
    course, lecturer, exam = setup_course_and_lecturer
    
    # Login
    client.post(
        "/auth/login",
        data={
            "login_type": "lecturer",
            "staff_id": "L100",
            "password": "Lect1!"
        }
    )
    
    # Create MCQ with missing option_b
    resp = client.post(
        f"/exams/{exam.id}/mcq/new",
        data={
            "question_text": "Valid question here",
            "option_a": "Option A",
            "option_b": "",  # missing
            "option_c": "Option C",
            "option_d": "Option D",
            "correct_option": "A"
        }
    )
    assert resp.status_code == 400
    assert "must be provided" in resp.text.lower() or "non-empty" in resp.text.lower()


@pytest.mark.usefixtures("cleanup_db")
def test_create_mcq_duplicate_options(client, setup_course_and_lecturer):
    """Test MCQ creation with duplicate options."""
    course, lecturer, exam = setup_course_and_lecturer
    
    # Login
    client.post(
        "/auth/login",
        data={
            "login_type": "lecturer",
            "staff_id": "L100",
            "password": "Lect1!"
        }
    )
    
    # Create MCQ with duplicate options
    resp = client.post(
        f"/exams/{exam.id}/mcq/new",
        data={
            "question_text": "Which of these is unique?",
            "option_a": "Same Option",
            "option_b": "Same Option",  # duplicate
            "option_c": "Unique C",
            "option_d": "Unique D",
            "correct_option": "C"
        }
    )
    assert resp.status_code == 400
    assert "must all be different" in resp.text.lower() or "unique" in resp.text.lower()


@pytest.mark.usefixtures("cleanup_db")
def test_create_mcq_short_question(client, setup_course_and_lecturer):
    """Test MCQ creation with question text too short."""
    course, lecturer, exam = setup_course_and_lecturer
    
    # Login
    client.post(
        "/auth/login",
        data={
            "login_type": "lecturer",
            "staff_id": "L100",
            "password": "Lect1!"
        }
    )
    
    # Create MCQ with too-short question
    resp = client.post(
        f"/exams/{exam.id}/mcq/new",
        data={
            "question_text": "abc",  # too short
            "option_a": "Option A",
            "option_b": "Option B",
            "option_c": "Option C",
            "option_d": "Option D",
            "correct_option": "A"
        }
    )
    assert resp.status_code == 400
    assert "at least 5 characters" in resp.text.lower() or "minimum length" in resp.text.lower()


@pytest.mark.usefixtures("cleanup_db")
def test_create_mcq_invalid_correct_option(client, setup_course_and_lecturer):
    """Test MCQ creation with invalid correct_option."""
    course, lecturer, exam = setup_course_and_lecturer
    
    # Login
    client.post(
        "/auth/login",
        data={
            "login_type": "lecturer",
            "staff_id": "L100",
            "password": "Lect1!"
        }
    )
    
    # Create MCQ with invalid correct_option
    resp = client.post(
        f"/exams/{exam.id}/mcq/new",
        data={
            "question_text": "What is a valid question?",
            "option_a": "Option A",
            "option_b": "Option B",
            "option_c": "Option C",
            "option_d": "Option D",
            "correct_option": "E"  # invalid
        }
    )
    assert resp.status_code == 400
    assert "one of a, b, c or d" in resp.text.lower() or "valid option" in resp.text.lower()


@pytest.mark.usefixtures("cleanup_db")
def test_create_mcq_strip_html_tags(client, setup_course_and_lecturer):
    """Test MCQ creation with HTML tags (security test)."""
    course, lecturer, exam = setup_course_and_lecturer
    
    # Login
    client.post(
        "/auth/login",
        data={
            "login_type": "lecturer",
            "staff_id": "L100",
            "password": "Lect1!"
        }
    )
    
    # Create MCQ with HTML/script tags
    resp = client.post(
        f"/exams/{exam.id}/mcq/new",
        data={
            "question_text": "<script>alert(1)</script>What is this question?",
            "option_a": "<b>Bold Option A</b>",
            "option_b": "<i>Italic B</i>",
            "option_c": "Normal C",
            "option_d": "Normal D",
            "correct_option": "C"
        }
    )
    assert resp.status_code == 303
    
    # Retrieve MCQ and verify tags are stripped
    resp_list = client.get(f"/exams/{exam.id}/mcq")
    assert "<script>" not in resp_list.text
    assert "<b>" not in resp_list.text
    assert "<i>" not in resp_list.text


@pytest.mark.usefixtures("cleanup_db")
def test_create_mcq_all_options_empty(client, setup_course_and_lecturer):
    """Test MCQ creation with all options empty."""
    course, lecturer, exam = setup_course_and_lecturer
    
    # Login
    client.post(
        "/auth/login",
        data={
            "login_type": "lecturer",
            "staff_id": "L100",
            "password": "Lect1!"
        }
    )
    
    # Create MCQ with all empty options
    resp = client.post(
        f"/exams/{exam.id}/mcq/new",
        data={
            "question_text": "Valid question text here",
            "option_a": "",
            "option_b": "",
            "option_c": "",
            "option_d": "",
            "correct_option": "A"
        }
    )
    assert resp.status_code == 400


@pytest.mark.usefixtures("cleanup_db")
def test_create_mcq_whitespace_only_option(client, setup_course_and_lecturer):
    """Test MCQ creation with whitespace-only option."""
    course, lecturer, exam = setup_course_and_lecturer
    
    # Login
    client.post(
        "/auth/login",
        data={
            "login_type": "lecturer",
            "staff_id": "L100",
            "password": "Lect1!"
        }
    )
    
    # Create MCQ with whitespace-only option
    resp = client.post(
        f"/exams/{exam.id}/mcq/new",
        data={
            "question_text": "Valid question text here",
            "option_a": "Valid",
            "option_b": "   ",  # whitespace only
            "option_c": "Valid",
            "option_d": "Valid",
            "correct_option": "A"
        }
    )
    assert resp.status_code == 400


@pytest.mark.usefixtures("cleanup_db")
def test_create_mcq_case_insensitive_correct_option(client, setup_course_and_lecturer):
    """Test MCQ creation with lowercase correct_option."""
    course, lecturer, exam = setup_course_and_lecturer
    
    # Login
    client.post(
        "/auth/login",
        data={
            "login_type": "lecturer",
            "staff_id": "L100",
            "password": "Lect1!"
        }
    )
    
    # Create MCQ with lowercase correct_option
    resp = client.post(
        f"/exams/{exam.id}/mcq/new",
        data={
            "question_text": "What is a valid question?",
            "option_a": "Option A",
            "option_b": "Option B",
            "option_c": "Option C",
            "option_d": "Option D",
            "correct_option": "b"  # lowercase
        }
    )
    # Should succeed if case-insensitive, or fail with 400 if case-sensitive
    assert resp.status_code in [303, 400]


@pytest.mark.usefixtures("cleanup_db")
def test_create_mcq_very_long_question(client, setup_course_and_lecturer):
    """Test MCQ creation with very long question text."""
    course, lecturer, exam = setup_course_and_lecturer
    
    # Login
    client.post(
        "/auth/login",
        data={
            "login_type": "lecturer",
            "staff_id": "L100",
            "password": "Lect1!"
        }
    )
    
    # Create MCQ with very long question
    long_question = "This is a very long question. " * 50  # ~1500 chars
    resp = client.post(
        f"/exams/{exam.id}/mcq/new",
        data={
            "question_text": long_question,
            "option_a": "Option A",
            "option_b": "Option B",
            "option_c": "Option C",
            "option_d": "Option D",
            "correct_option": "A"
        }
    )
    # Should succeed or fail with validation error depending on max_length
    assert resp.status_code in [303, 400]


@pytest.mark.usefixtures("cleanup_db")
def test_create_mcq_special_characters(client, setup_course_and_lecturer):
    """Test MCQ creation with special characters."""
    course, lecturer, exam = setup_course_and_lecturer
    
    # Login
    client.post(
        "/auth/login",
        data={
            "login_type": "lecturer",
            "staff_id": "L100",
            "password": "Lect1!"
        }
    )
    
    # Create MCQ with special characters
    resp = client.post(
        f"/exams/{exam.id}/mcq/new",
        data={
            "question_text": r"What is 2+2=? & <> \\ / \" '",
            "option_a": "Option with @#$%",
            "option_b": "Option with éàü",
            "option_c": "Option with 中文",
            "option_d": "Normal option",
            "correct_option": "D"
        }
    )
    assert resp.status_code in [303, 400]
