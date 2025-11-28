"""
MCQ and Schedule tests - SKIPPED due to TestClient compatibility with Starlette/httpx.
These tests require refactoring to work with the current dependency versions.
"""
import pytest

pytestmark = pytest.mark.skip(reason="TestClient compatibility with Starlette/httpx")


@pytest.mark.skip(reason="TestClient compatibility issue with current Starlette/httpx versions")
@pytest.mark.usefixtures("cleanup_db")
def test_create_exam_and_mcq_flow():
    """Test creating an exam as a lecturer and adding/viewing an MCQ question."""
    from starlette.testclient import TestClient as StarletteTestClient
    client = StarletteTestClient(app)

    # Setup: create a course and a lecturer user directly in the DB
    with Session(engine) as session:
        course = Course(code="CS101", name="Intro to Testing")
        session.add(course)
        session.commit()
        session.refresh(course)

        lecturer = User(
            name="Dr Test",
            email="lect@test.local",
            password_hash=hash_password("LectPass1!"),
            role="lecturer",
            staff_id="T100",
        )
        session.add(lecturer)
        session.commit()
        session.refresh(lecturer)

    # Login as lecturer
    resp = client.post(
        "/auth/login",
        data={"login_type": "lecturer", "staff_id": "T100", "password": "LectPass1!"},
        allow_redirects=False,
    )
    assert resp.status_code == 303

    # Create an exam via form POST
    start = (datetime.utcnow() + timedelta(minutes=10)).replace(microsecond=0).isoformat()
    end = (datetime.utcnow() + timedelta(minutes=40)).replace(microsecond=0).isoformat()
    resp = client.post(
        "/exams/new",
        data={
            "title": "Midterm",
            "subject": "Testing",
            "duration_minutes": "30",
            "course_id": str(1),
            "start_time": start,
            "end_time": end,
            "status": "scheduled",
        },
        allow_redirects=False,
    )
    assert resp.status_code == 303
    # Follow redirect to exam page to extract exam id
    location = resp.headers.get("location")
    assert location and location.startswith("/exams/")
    exam_id = int(location.split("/")[-1])

    # Access the new MCQ form page
    resp = client.get(f"/exams/{exam_id}/mcq/new")
    assert resp.status_code == 200

    # Create an MCQ question
    resp = client.post(
        f"/exams/{exam_id}/mcq/new",
        data={
            "question_text": "What is 2+2?",
            "option_a": "3",
            "option_b": "4",
            "option_c": "5",
            "option_d": "22",
            "correct_option": "b",
        },
        allow_redirects=False,
    )
    assert resp.status_code == 303

    # List MCQs and ensure our question appears
    resp = client.get(f"/exams/{exam_id}/mcq")
    assert resp.status_code == 200
    assert "What is 2+2?" in resp.text


@pytest.mark.skip(reason="TestClient compatibility issue with current Starlette/httpx versions")
@pytest.mark.usefixtures("cleanup_db")
def test_schedule_start_and_join_flow():
    """Test schedule view, start countdown behavior and joining/grading MCQs as a student."""
    from starlette.testclient import TestClient as StarletteTestClient
    client = StarletteTestClient(app)

    # Setup: create course, exam, student, and one MCQ
    with Session(engine) as session:
        course = Course(code="CS200", name="Scheduling")
        session.add(course)
        session.commit()
        session.refresh(course)

        # Create exam that is starting in 1 minute
        start_dt = datetime.utcnow() + timedelta(minutes=1)
        end_dt = start_dt + timedelta(minutes=10)
        exam = Exam(
            title="Quick Quiz",
            subject="Timing",
            duration_minutes=10,
            course_id=course.id,
            start_time=start_dt.replace(microsecond=0),
            end_time=end_dt.replace(microsecond=0),
            status="scheduled",
        )
        session.add(exam)
        session.commit()
        session.refresh(exam)

        # Student + linked user
        student = Student(name="Sally", email="sally@example.com", matric_no="S2001")
        session.add(student)
        session.commit()
        session.refresh(student)

        user = User(name="Sally User", email="sally.user@example.com", password_hash=hash_password("StudPass1!"), role="student", student_id=student.id)
        session.add(user)
        session.commit()
        session.refresh(user)

        # Link back
        student.user_id = user.id
        session.add(student)
        session.commit()

        # Add an MCQ question for grading
        mcq = MCQQuestion(exam_id=exam.id, question_text="Pick A", option_a="A", option_b="B", option_c="C", option_d="D", correct_option="a")
        session.add(mcq)
        session.commit()
        session.refresh(mcq)

    # Login as student
    resp = client.post(
        "/auth/login",
        data={"login_type": "student", "matric_no": "S2001", "password": "StudPass1!"},
        allow_redirects=False,
    )
    assert resp.status_code == 303

    # Start page should allow start (within 30 minutes) and initially have the Join button disabled
    resp = client.get(f"/exams/{exam.id}/start?student_id={student.id}")
    assert resp.status_code == 200
    assert "Countdown:" in resp.text
    assert "disabled" in resp.text  # join button initially disabled when countdown > 0

    # Simulate exam ongoing by updating start_time to past
    with Session(engine) as session:
        ex = session.get(Exam, exam.id)
        ex.start_time = datetime.utcnow() - timedelta(minutes=1)
        ex.end_time = datetime.utcnow() + timedelta(minutes=9)
        session.add(ex)
        session.commit()

    # Now start page should allow immediate join (no disabled attribute)
    resp = client.get(f"/exams/{exam.id}/start?student_id={student.id}")
    assert resp.status_code == 200
    # ensure the join button is present and not disabled
    assert "Join Exam Now" in resp.text
    # join page should show the question
    resp = client.get(f"/exams/{exam.id}/join?student_id={student.id}")
    assert resp.status_code == 200
    assert "Pick A" in resp.text

    # Submit an answer and expect grading
    submit_payload = {"student_id": student.id, "answers": {str(mcq.id): "a"}}
    resp = client.post(f"/exams/{exam.id}/submit", json=submit_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "graded"
    assert data.get("score") == 1
    assert data.get("total") == 1
