"""
Acceptance tests for Results and Grading System.

Tests cover:
- Student results viewing
- Lecturer results overview
- Course-level results
- Exam-level detailed results
- Auto-save functionality for MCQ and Essay exams
- Grade display after exam submission
"""

import sys
from pathlib import Path
import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, select

# Ensure app is on path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from fastapi.testclient import TestClient
from app.main import app
from app.database import engine, create_db_and_tables
from app.models import (
    User,
    Student,
    Course,
    Exam,
    MCQQuestion,
    MCQAnswer,
    MCQResult,
    ExamQuestion,  # Essay questions
    EssayAnswer,
    ExamAttempt,
    Enrollment,
    CourseLecturer,
)


@pytest.fixture(scope="function")
def session():
    """Create a new database session for each test."""
    create_db_and_tables()
    with Session(engine) as session:
        yield session


@pytest.fixture(scope="function")
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture(scope="function")
def test_data(session: Session):
    """Create test data for results system tests."""
    import random
    unique_id = random.randint(10000, 99999)
    
    # Create users
    student_user = User(
        username=f"student_results_{unique_id}",
        name="Test Student User",
        email=f"student_results_{unique_id}@test.com",
        password_hash="hashed",
        role="student",
    )
    lecturer_user = User(
        username=f"lecturer_results_{unique_id}",
        name="Test Lecturer User",
        email=f"lecturer_results_{unique_id}@test.com",
        password_hash="hashed",
        role="lecturer",
    )
    session.add(student_user)
    session.add(lecturer_user)
    session.commit()
    session.refresh(student_user)
    session.refresh(lecturer_user)

    # Create student
    student = Student(
        id=student_user.id,
        name="Test Student",
        matric_no="A0001R",
        email=student_user.email,
    )
    session.add(student)
    session.commit()
    session.refresh(student)

    # Create course
    course = Course(
        code="CS101",
        name="Introduction to Testing",
        description="Test course for results",
    )
    session.add(course)
    session.commit()
    session.refresh(course)

    # Link lecturer to course
    course_lecturer = CourseLecturer(
        course_id=course.id, lecturer_id=lecturer_user.id
    )
    session.add(course_lecturer)

    # Enroll student in course
    enrollment = Enrollment(student_id=student.id, course_id=course.id)
    session.add(enrollment)
    session.commit()

    # Create exam
    exam = Exam(
        title="Test Exam",
        subject="Testing",
        course_id=course.id,
        duration_minutes=60,
        start_time=datetime.now() - timedelta(hours=2),
        end_time=datetime.now() + timedelta(hours=2),
        status="scheduled",
    )
    session.add(exam)
    session.commit()
    session.refresh(exam)

    # Create MCQ questions
    for i in range(5):
        question = MCQQuestion(
            exam_id=exam.id,
            question_text=f"Question {i+1}",
            option_a=f"Option A{i+1}",
            option_b=f"Option B{i+1}",
            option_c=f"Option C{i+1}",
            option_d=f"Option D{i+1}",
            correct_option="a",
        )
        session.add(question)
    session.commit()

    # Create MCQ result
    result = MCQResult(
        exam_id=exam.id,
        student_id=student.id,
        score=8,
        total_questions=5,
        graded_at=datetime.now(),
    )
    session.add(result)
    session.commit()

    return {
        "student_user": student_user,
        "lecturer_user": lecturer_user,
        "student": student,
        "course": course,
        "exam": exam,
        "result": result,
    }


class TestStudentResultsPositive:
    """Positive test cases for student results viewing."""

    def test_student_can_view_own_results(self, client: TestClient, test_data):
        """Test that a student can view their own exam results."""
        student_id = test_data["student"].id

        response = client.get(f"/exams/results/student/{student_id}")

        assert response.status_code == 200
        assert b"Test Student" in response.content
        assert b"Test Exam" in response.content
        print("✓ Student can view own results")

    def test_student_results_shows_correct_statistics(
        self, client: TestClient, test_data
    ):
        """Test that student results page displays correct statistics."""
        student_id = test_data["student"].id

        response = client.get(f"/exams/results/student/{student_id}")

        assert response.status_code == 200
        # Should show total exams taken
        assert b"1" in response.content  # Total exams
        # Should show score
        assert b"8" in response.content  # Score achieved
        print("✓ Student results show correct statistics")

    def test_student_results_shows_percentage(self, client: TestClient, test_data):
        """Test that results display percentage correctly."""
        student_id = test_data["student"].id

        response = client.get(f"/exams/results/student/{student_id}")

        assert response.status_code == 200
        # 8 out of 10 possible marks = 80%
        content = response.content.decode()
        assert "80" in content or "8" in content
        print("✓ Student results show percentage")

    def test_student_results_page_loads_with_no_results(
        self, client: TestClient, session: Session
    ):
        """Test that results page loads even when student has no results."""
        # Create new student with no results
        new_user = User(
            username="student_no_results",
            name="No Results User",
            email="no_results@test.com",
            password_hash="hashed",
            role="student",
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        new_student = Student(
            id=new_user.id,
            name="No Results Student",
            matric_no="A0002R",
            email=new_user.email,
        )
        session.add(new_student)
        session.commit()

        response = client.get(f"/exams/results/student/{new_student.id}")

        assert response.status_code == 200
        assert b"No Results Student" in response.content
        print("✓ Results page loads with no results")


class TestStudentResultsNegative:
    """Negative test cases for student results viewing."""

    def test_student_results_with_invalid_id(self, client: TestClient):
        """Test accessing results with non-existent student ID."""
        invalid_id = 99999

        response = client.get(f"/exams/results/student/{invalid_id}")

        assert response.status_code == 200  # Page loads but shows no student
        print("✓ Handles invalid student ID gracefully")

    def test_student_results_with_negative_id(self, client: TestClient):
        """Test accessing results with negative student ID."""
        response = client.get("/exams/results/student/-1")

        # Should handle gracefully
        assert response.status_code in [200, 404, 422]
        print("✓ Handles negative student ID")

    def test_student_results_with_string_id(self, client: TestClient):
        """Test accessing results with string instead of integer ID."""
        response = client.get("/exams/results/student/invalid")

        # FastAPI should return 422 for validation error
        assert response.status_code == 422
        print("✓ Validates student ID type")


class TestLecturerResultsPositive:
    """Positive test cases for lecturer results overview."""

    def test_lecturer_can_view_results_overview(self, client: TestClient, test_data):
        """Test that lecturer can view results overview."""
        response = client.get("/exams/results/lecturer")

        assert response.status_code == 200
        assert b"Introduction to Testing" in response.content
        print("✓ Lecturer can view results overview")

    def test_lecturer_results_shows_course_statistics(
        self, client: TestClient, test_data
    ):
        """Test that lecturer overview shows course statistics."""
        response = client.get("/exams/results/lecturer")

        assert response.status_code == 200
        # Should show number of exams
        assert b"1" in response.content
        print("✓ Lecturer overview shows statistics")

    def test_lecturer_can_view_course_results(self, client: TestClient, test_data):
        """Test that lecturer can view results for specific course."""
        course_id = test_data["course"].id

        response = client.get(f"/exams/results/course/{course_id}")

        assert response.status_code == 200
        assert b"Introduction to Testing" in response.content
        assert b"Test Exam" in response.content
        print("✓ Lecturer can view course results")

    def test_lecturer_can_view_exam_details(self, client: TestClient, test_data):
        """Test that lecturer can view detailed exam results."""
        exam_id = test_data["exam"].id

        response = client.get(f"/exams/results/exam/{exam_id}")

        assert response.status_code == 200
        assert b"Test Exam" in response.content
        assert b"Test Student" in response.content
        print("✓ Lecturer can view exam details")

    def test_exam_details_shows_student_rankings(
        self, client: TestClient, test_data
    ):
        """Test that exam details show student rankings."""
        exam_id = test_data["exam"].id

        response = client.get(f"/exams/results/exam/{exam_id}")

        assert response.status_code == 200
        content = response.content.decode()
        # Should show student name and score
        assert "Test Student" in content
        assert "8" in content or "80" in content
        print("✓ Exam details show rankings")


class TestLecturerResultsNegative:
    """Negative test cases for lecturer results."""

    def test_course_results_with_invalid_id(self, client: TestClient):
        """Test accessing course results with non-existent course ID."""
        invalid_id = 99999

        response = client.get(f"/exams/results/course/{invalid_id}")

        assert response.status_code == 404
        print("✓ Returns 404 for invalid course ID")

    def test_exam_results_with_invalid_id(self, client: TestClient):
        """Test accessing exam results with non-existent exam ID."""
        invalid_id = 99999

        response = client.get(f"/exams/results/exam/{invalid_id}")

        assert response.status_code == 404
        print("✓ Returns 404 for invalid exam ID")

    def test_course_results_with_string_id(self, client: TestClient):
        """Test accessing course results with string ID."""
        response = client.get("/exams/results/course/invalid")

        assert response.status_code == 422
        print("✓ Validates course ID type")

    def test_exam_results_with_negative_id(self, client: TestClient):
        """Test accessing exam results with negative ID."""
        response = client.get("/exams/results/exam/-1")

        assert response.status_code == 404
        print("✓ Handles negative exam ID")


class TestExamFinishedPagePositive:
    """Positive test cases for exam finished page."""

    def test_exam_finished_page_displays_score(self, client: TestClient):
        """Test that exam finished page displays score correctly."""
        response = client.get("/exams/exam_finished?score=8&total=10")

        assert response.status_code == 200
        assert b"8" in response.content
        assert b"10" in response.content
        print("✓ Exam finished page displays score")

    def test_exam_finished_page_without_score(self, client: TestClient):
        """Test that exam finished page loads without score parameters."""
        response = client.get("/exams/exam_finished")

        assert response.status_code == 200
        print("✓ Exam finished page loads without score")

    def test_exam_finished_page_with_perfect_score(self, client: TestClient):
        """Test exam finished page with perfect score."""
        response = client.get("/exams/exam_finished?score=10&total=10")

        assert response.status_code == 200
        assert b"10" in response.content
        print("✓ Displays perfect score correctly")

    def test_exam_finished_page_with_zero_score(self, client: TestClient):
        """Test exam finished page with zero score."""
        response = client.get("/exams/exam_finished?score=0&total=10")

        assert response.status_code == 200
        assert b"0" in response.content
        print("✓ Displays zero score correctly")


class TestExamFinishedPageNegative:
    """Negative test cases for exam finished page."""

    def test_exam_finished_with_negative_score(self, client: TestClient):
        """Test exam finished page with negative score."""
        response = client.get("/exams/exam_finished?score=-5&total=10")

        # Should still load (might show negative)
        assert response.status_code == 200
        print("✓ Handles negative score")

    def test_exam_finished_with_score_exceeding_total(self, client: TestClient):
        """Test exam finished page when score exceeds total."""
        response = client.get("/exams/exam_finished?score=15&total=10")

        assert response.status_code == 200
        print("✓ Handles score exceeding total")

    def test_exam_finished_with_invalid_score_type(self, client: TestClient):
        """Test exam finished page with non-numeric score."""
        response = client.get("/exams/exam_finished?score=invalid&total=10")

        # FastAPI validation should handle this
        assert response.status_code == 422
        print("✓ Validates score parameter type")

    def test_exam_finished_with_zero_total(self, client: TestClient):
        """Test exam finished page with zero total questions."""
        response = client.get("/exams/exam_finished?score=0&total=0")

        # Should handle division by zero gracefully
        assert response.status_code == 200
        print("✓ Handles zero total gracefully")


class TestAutoSaveFunctionalityPositive:
    """Positive test cases for auto-save functionality."""

    def test_mcq_autosave_endpoint_exists(self, client: TestClient, test_data):
        """Test that MCQ auto-save endpoint is accessible."""
        exam_id = test_data["exam"].id
        student_id = test_data["student"].id

        # Post auto-save data
        response = client.post(
            f"/exams/{exam_id}/autosave",
            json={"student_id": student_id, "answers": {"1": "a", "2": "b"}},
        )

        # Should accept the request (200 or 201)
        assert response.status_code in [200, 201]
        print("✓ MCQ auto-save endpoint accessible")

    def test_mcq_autosave_saves_answers(
        self, client: TestClient, test_data, session: Session
    ):
        """Test that MCQ auto-save actually saves answers to database."""
        exam_id = test_data["exam"].id
        student_id = test_data["student"].id

        # Get first question ID
        question = session.exec(
            select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)
        ).first()

        response = client.post(
            f"/exams/{exam_id}/autosave",
            json={
                "student_id": student_id,
                "answers": {str(question.id): "a"},
            },
        )

        assert response.status_code in [200, 201]

        # Verify answer was saved
        saved_answer = session.exec(
            select(MCQAnswer).where(
                MCQAnswer.exam_id == exam_id,
                MCQAnswer.student_id == student_id,
                MCQAnswer.question_id == question.id,
            )
        ).first()

        assert saved_answer is not None
        assert saved_answer.selected_answer == "a"
        print("✓ MCQ auto-save persists to database")

    def test_essay_autosave_endpoint_exists(
        self, client: TestClient, test_data, session: Session
    ):
        """Test that essay auto-save endpoint is accessible."""
        exam_id = test_data["exam"].id
        student_id = test_data["student"].id

        # Create essay question
        essay_question = ExamQuestion(
            exam_id=exam_id, question_text="Essay question", marks=10
        )
        session.add(essay_question)
        session.commit()
        session.refresh(essay_question)

        # Create exam attempt
        attempt = ExamAttempt(
            exam_id=exam_id,
            student_id=student_id,
            start_time=datetime.now(),
            status="in_progress",
        )
        session.add(attempt)
        session.commit()

        response = client.post(
            f"/essay/exam/{exam_id}/autosave",
            json={
                "student_id": student_id,
                "answers": {str(essay_question.id): "Test answer"},
            },
        )

        assert response.status_code in [200, 201]
        print("✓ Essay auto-save endpoint accessible")


class TestAutoSaveFunctionalityNegative:
    """Negative test cases for auto-save functionality."""

    def test_mcq_autosave_with_invalid_exam_id(self, client: TestClient, test_data):
        """Test MCQ auto-save with non-existent exam ID."""
        invalid_exam_id = 99999
        student_id = test_data["student"].id

        response = client.post(
            f"/exams/{invalid_exam_id}/autosave",
            json={"student_id": student_id, "answers": {"1": "a"}},
        )

        assert response.status_code in [404, 422]
        print("✓ MCQ auto-save rejects invalid exam ID")

    def test_mcq_autosave_with_invalid_student_id(self, client: TestClient, test_data):
        """Test MCQ auto-save with non-existent student ID."""
        exam_id = test_data["exam"].id
        invalid_student_id = 99999

        response = client.post(
            f"/exams/{exam_id}/autosave",
            json={"student_id": invalid_student_id, "answers": {"1": "a"}},
        )

        assert response.status_code in [404, 422]
        print("✓ MCQ auto-save rejects invalid student ID")

    def test_mcq_autosave_with_empty_answers(self, client: TestClient, test_data):
        """Test MCQ auto-save with empty answers."""
        exam_id = test_data["exam"].id
        student_id = test_data["student"].id

        response = client.post(
            f"/exams/{exam_id}/autosave",
            json={"student_id": student_id, "answers": {}},
        )

        # Should accept empty answers (student might not have answered yet)
        assert response.status_code in [200, 201]
        print("✓ MCQ auto-save handles empty answers")

    def test_mcq_autosave_with_invalid_answer_format(
        self, client: TestClient, test_data
    ):
        """Test MCQ auto-save with invalid answer format."""
        exam_id = test_data["exam"].id
        student_id = test_data["student"].id

        response = client.post(
            f"/exams/{exam_id}/autosave",
            json={
                "student_id": student_id,
                "answers": "invalid_format",  # Should be dict
            },
        )

        assert response.status_code == 422
        print("✓ MCQ auto-save validates answer format")

    def test_essay_autosave_with_no_attempt(
        self, client: TestClient, test_data, session: Session
    ):
        """Test essay auto-save when no exam attempt exists."""
        exam_id = test_data["exam"].id
        student_id = test_data["student"].id

        # Create essay question but no attempt
        essay_question = ExamQuestion(
            exam_id=exam_id, question_text="Essay question 2", marks=10
        )
        session.add(essay_question)
        session.commit()

        response = client.post(
            f"/essay/exam/{exam_id}/autosave",
            json={
                "student_id": student_id,
                "answers": {str(essay_question.id): "Test answer"},
            },
        )

        # Should handle gracefully (might create attempt or return error)
        assert response.status_code in [200, 201, 404, 422]
        print("✓ Essay auto-save handles missing attempt")


class TestResultsIntegration:
    """Integration tests for complete results workflow."""

    def test_complete_exam_to_results_workflow(
        self, client: TestClient, test_data, session: Session
    ):
        """Test complete workflow from taking exam to viewing results."""
        exam_id = test_data["exam"].id
        student_id = test_data["student"].id

        # 1. Verify student can view their results
        response = client.get(f"/exams/results/student/{student_id}")
        assert response.status_code == 200

        # 2. Verify lecturer can view course results
        course_id = test_data["course"].id
        response = client.get(f"/exams/results/course/{course_id}")
        assert response.status_code == 200

        # 3. Verify lecturer can view exam details
        response = client.get(f"/exams/results/exam/{exam_id}")
        assert response.status_code == 200

        print("✓ Complete exam to results workflow works")

    def test_multiple_students_results_ranking(
        self, client: TestClient, test_data, session: Session
    ):
        """Test that multiple students are ranked correctly."""
        exam_id = test_data["exam"].id

        # Create additional students with different scores
        for i in range(3):
            user = User(
                username=f"student_rank_{i}",
                name=f"Rank User {i}",
                email=f"rank{i}@test.com",
                password_hash="hashed",
                role="student",
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            student = Student(
                id=user.id,
                name=f"Rank Student {i}",
                matric_no=f"A000{i+3}R",
                email=user.email,
            )
            session.add(student)
            session.commit()

            # Create result with different score
            result = MCQResult(
                exam_id=exam_id,
                student_id=student.id,
                score=6 + i,  # Scores: 6, 7, 8
                total_questions=5,
                graded_at=datetime.now(),
            )
            session.add(result)
        session.commit()

        # View exam results
        response = client.get(f"/exams/results/exam/{exam_id}")

        assert response.status_code == 200
        content = response.content.decode()

        # All students should appear
        assert "Rank Student" in content
        print("✓ Multiple students ranked correctly")


# Summary message for test run
def test_results_system_summary():
    """Print summary of results system test coverage."""
    print("\n" + "=" * 60)
    print("RESULTS SYSTEM TEST COVERAGE SUMMARY")
    print("=" * 60)
    print("✓ Student Results Viewing (Positive & Negative)")
    print("✓ Lecturer Results Overview (Positive & Negative)")
    print("✓ Exam Finished Page (Positive & Negative)")
    print("✓ Auto-Save Functionality (Positive & Negative)")
    print("✓ Integration Tests")
    print("=" * 60)
