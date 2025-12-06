import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.database import engine
from app.auth_utils import hash_password
from app.models import Course, User, Student, Exam, MCQQuestion

@pytest.mark.usefixtures("cleanup_db_between_tests")
def create_sample_course_and_lecturer(session: Session = None):
    # helper to insert a course and lecturer; return (course_id, lecturer_credentials)
    with Session(engine) as s:
        course = Course(code="TST100", name="Test Course")
        s.add(course)
        s.commit()
        s.refresh(course)
        lecturer = User(name="Test L", email="lect@x", password_hash=hash_password("Lect1!"), role="lecturer", staff_id="L100")
        s.add(lecturer)
        s.commit()
        s.refresh(lecturer)
        return course, lecturer

# 1) Success case
@pytest.mark.usefixtures("cleanup_db_between_tests")
def test_create_mcq_success():
    client = TestClient(app)
    # create data
    with Session(engine) as s:
        course = Course(code="CS101", name="C")
        s.add(course); s.commit(); s.refresh(course)
        lecturer = User(name="L", email="l@x", password_hash=hash_password("Lect1!"), role="lecturer", staff_id="S1")
        s.add(lecturer); s.commit(); s.refresh(lecturer)
        # create exam
        exam = Exam(title="E", subject="S", duration_minutes=10, course_id=course.id)
        s.add(exam); s.commit(); s.refresh(exam)

    # simulate login by posting to /auth/login (if sessions used), then create MCQ
    resp_login = client.post("/auth/login", data={"login_type": "lecturer", "staff_id": "S1", "password": "Lect1!"}, allow_redirects=False)
    assert resp_login.status_code == 303

    resp = client.post(f"/exams/{exam.id}/mcq/new", data={
        "question_text": "What is 1+1?",
        "option_a": "1",
        "option_b": "2",
        "option_c": "3",
        "option_d": "4",
        "correct_option": "B"
    }, allow_redirects=False)
    assert resp.status_code == 303  # redirected to mcq list

# 2) Missing/empty option -> server error
@pytest.mark.usefixtures("cleanup_db_between_tests")
def test_create_mcq_missing_option():
    client = TestClient(app)
    with Session(engine) as s:
        course = Course(code="CSX", name="C"); s.add(course); s.commit(); s.refresh(course)
        lec = User(name="L", email="l2@x", password_hash=hash_password("Lect1!"), role="lecturer", staff_id="S2")
        s.add(lec); s.commit(); s.refresh(lec)
        exam = Exam(title="E", subject="S", duration_minutes=10, course_id=course.id)
        s.add(exam); s.commit(); s.refresh(exam)
    client.post("/auth/login", data={"login_type":"lecturer","staff_id":"S2","password":"Lect1!"}, allow_redirects=False)
    resp = client.post(f"/exams/{exam.id}/mcq/new", data={
        "question_text": "Valid question",
        "option_a": "A",
        "option_b": "",  # missing
        "option_c": "C",
        "option_d": "D",
        "correct_option": "A"
    })
    assert resp.status_code == 400
    assert "All options must be provided" in resp.text or "All options must be provided and non-empty" in resp.text

# 3) Duplicate options -> server error
@pytest.mark.usefixtures("cleanup_db_between_tests")
def test_create_mcq_duplicate_options():
    client = TestClient(app)
    with Session(engine) as s:
        course = Course(code="CSY", name="C"); s.add(course); s.commit(); s.refresh(course)
        lec = User(name="L", email="l3@x", password_hash=hash_password("Lect1!"), role="lecturer", staff_id="S3")
        s.add(lec); s.commit(); s.refresh(lec)
        exam = Exam(title="E", subject="S", duration_minutes=10, course_id=course.id)
        s.add(exam); s.commit(); s.refresh(exam)
    client.post("/auth/login", data={"login_type":"lecturer","staff_id":"S3","password":"Lect1!"}, allow_redirects=False)
    resp = client.post(f"/exams/{exam.id}/mcq/new", data={
        "question_text": "Q",
        "option_a": "Same",
        "option_b": "Same",
        "option_c": "C",
        "option_d": "D",
        "correct_option": "A"
    })
    assert resp.status_code == 400
    assert "must all be different" in resp.text

# 4) Too-short question -> server error
@pytest.mark.usefixtures("cleanup_db_between_tests")
def test_create_mcq_short_question():
    client = TestClient(app)
    with Session(engine) as s:
        course = Course(code="CSS", name="C"); s.add(course); s.commit(); s.refresh(course)
        lec = User(name="L", email="l4@x", password_hash=hash_password("Lect1!"), role="lecturer", staff_id="S4")
        s.add(lec); s.commit(); s.refresh(lec)
        exam = Exam(title="E", subject="S", duration_minutes=10, course_id=course.id)
        s.add(exam); s.commit(); s.refresh(exam)
    client.post("/auth/login", data={"login_type":"lecturer","staff_id":"S4","password":"Lect1!"}, allow_redirects=False)
    resp = client.post(f"/exams/{exam.id}/mcq/new", data={
        "question_text": "abc",  # too short
        "option_a": "A",
        "option_b": "B",
        "option_c": "C",
        "option_d": "D",
        "correct_option": "A"
    })
    assert resp.status_code == 400
    assert "at least 5 characters" in resp.text

# 5) Correct option mismatch -> server error
@pytest.mark.usefixtures("cleanup_db_between_tests")
def test_create_mcq_invalid_correct_option():
    client = TestClient(app)
    with Session(engine) as s:
        course = Course(code="CD", name="C"); s.add(course); s.commit(); s.refresh(course)
        lec = User(name="L", email="l5@x", password_hash=hash_password("Lect1!"), role="lecturer", staff_id="S5")
        s.add(lec); s.commit(); s.refresh(lec)
        exam = Exam(title="E", subject="S", duration_minutes=10, course_id=course.id)
        s.add(exam); s.commit(); s.refresh(exam)
    client.post("/auth/login", data={"login_type":"lecturer","staff_id":"S5","password":"Lect1!"}, allow_redirects=False)
    # correct_option 'E' invalid
    resp = client.post(f"/exams/{exam.id}/mcq/new", data={
        "question_text": "Valid question",
        "option_a": "A",
        "option_b": "B",
        "option_c": "C",
        "option_d": "D",
        "correct_option": "E"
    })
    assert resp.status_code == 400
    assert "one of A, B, C or D" in resp.text

# 6) HTML stripping (security)
@pytest.mark.usefixtures("cleanup_db_between_tests")
def test_create_mcq_strip_html_tags():
    client = TestClient(app)
    with Session(engine) as s:
        course = Course(code="CH", name="C"); s.add(course); s.commit(); s.refresh(course)
        lec = User(name="L", email="l6@x", password_hash=hash_password("Lect1!"), role="lecturer", staff_id="S6")
        s.add(lec); s.commit(); s.refresh(lec)
        exam = Exam(title="E", subject="S", duration_minutes=10, course_id=course.id)
        s.add(exam); s.commit(); s.refresh(exam)
    client.post("/auth/login", data={"login_type":"lecturer","staff_id":"S6","password":"Lect1!"}, allow_redirects=False)
    resp = client.post(f"/exams/{exam.id}/mcq/new", data={
        "question_text": "<script>alert(1)</script>Q",
        "option_a": "<b>A</b>",
        "option_b": "B",
        "option_c": "C",
        "option_d": "D",
        "correct_option": "A"
    }, allow_redirects=False)
    assert resp.status_code == 303
    # retrieve mcq list and ensure tags removed
    r2 = client.get(f"/exams/{exam.id}/mcq")
    assert "<script>" not in r2.text
    assert "<b>A</b>" not in r2.text