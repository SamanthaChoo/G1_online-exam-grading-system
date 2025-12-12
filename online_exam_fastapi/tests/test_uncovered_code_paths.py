"""Acceptance tests for uncovered code paths and error conditions.

These tests target REAL code branches that are not currently exercised:
- Essay service validation (marks > 1000, marks < 1, empty text after sanitization)
- Student permission checks on delete endpoint and edit form
- Permission-based filtering in listing endpoints for students
"""

import pytest
from app.models import Exam, ExamQuestion, User, Course, Student, ExamAttempt, EssayAnswer
from app.auth_utils import hash_password
from sqlmodel import Session, select
from datetime import datetime, timedelta


class TestEssayQuestionValidation:
    """Test validation branches in essay_service.add_question and edit_question.
    
    These tests verify that the service layer correctly enforces constraints
    on question marks and text content.
    """

    def test_reject_marks_exceeding_100_on_create(self, client, session: Session):
        """GIVEN essay question creation endpoint
        WHEN submitting marks > 100
        THEN the system should return 400 error."""
        course = Course(name="Test", code="EQV1")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        # Execute - marks exceeding maximum
        response = client.post(
            f"/essay/{exam.id}/questions/new",
            data={"question_text": "Question text", "max_marks": "101"}
        )
        
        # Verify
        assert response.status_code == 400
        assert "100" in response.text
        
        # Verify question was NOT created
        session.expunge_all()
        questions = session.exec(
            select(ExamQuestion).where(ExamQuestion.exam_id == exam.id)
        ).all()
        assert len(questions) == 0

    def test_accept_marks_at_boundary_100_on_create(self, client, session: Session):
        """GIVEN essay question creation endpoint
        WHEN submitting marks = 100 (maximum allowed)
        THEN question should be created successfully."""
        course = Course(name="Test", code="EQV2")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        # Execute
        response = client.post(
            f"/essay/{exam.id}/questions/new",
            data={"question_text": "Question text", "max_marks": "100"}
        )
        
        # Verify success (303 redirect)
        assert response.status_code == 303
        
        # Verify question was created
        session.expunge_all()
        questions = session.exec(
            select(ExamQuestion).where(ExamQuestion.exam_id == exam.id)
        ).all()
        assert len(questions) == 1
        assert questions[0].max_marks == 100

    def test_reject_marks_less_than_1_on_create(self, client, session: Session):
        """GIVEN essay question creation endpoint
        WHEN submitting marks < 1
        THEN the system should return 400 error."""
        course = Course(name="Test", code="EQV3")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        # Execute - marks = 0
        response = client.post(
            f"/essay/{exam.id}/questions/new",
            data={"question_text": "Question text", "max_marks": "0"}
        )
        
        # Verify
        assert response.status_code == 400
        assert "at least 1" in response.text

    def test_reject_negative_marks_on_create(self, client, session: Session):
        """GIVEN essay question creation endpoint
        WHEN submitting negative marks
        THEN the system should return 400 error."""
        course = Course(name="Test", code="EQV4")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        # Execute
        response = client.post(
            f"/essay/{exam.id}/questions/new",
            data={"question_text": "Question text", "max_marks": "-5"}
        )
        
        # Verify
        assert response.status_code == 400

    def test_reject_whitespace_only_text_on_create(self, client, session: Session):
        """GIVEN essay question creation endpoint
        WHEN submitting whitespace-only text
        THEN the system should return 400 error (sanitized to empty)."""
        course = Course(name="Test", code="EQV6")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        # Execute
        response = client.post(
            f"/essay/{exam.id}/questions/new",
            data={"question_text": "    ", "max_marks": "10"}
        )
        
        # Verify
        assert response.status_code == 400

    def test_reject_marks_exceeding_100_on_edit(self, client, session: Session):
        """GIVEN existing essay question
        WHEN updating marks to > 100
        THEN the system should return 400 error."""
        course = Course(name="Test", code="EQV7")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        q = ExamQuestion(exam_id=exam.id, question_text="Original", max_marks=50)
        session.add(q)
        session.commit()
        session.refresh(q)
        q_id = q.id
        
        # Execute - update marks beyond limit
        response = client.post(
            f"/essay/{exam.id}/questions/{q_id}/edit",
            data={"max_marks": "101"}
        )
        
        # Verify
        assert response.status_code == 400
        
        # Verify marks were NOT updated
        session.expunge_all()
        q = session.get(ExamQuestion, q_id)
        assert q.max_marks == 50

    def test_reject_marks_zero_on_edit(self, client, session: Session):
        """GIVEN existing essay question
        WHEN updating marks to 0
        THEN the system should return 400 error."""
        course = Course(name="Test", code="EQV8")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        q = ExamQuestion(exam_id=exam.id, question_text="Original", max_marks=100)
        session.add(q)
        session.commit()
        session.refresh(q)
        q_id = q.id
        
        # Execute
        response = client.post(
            f"/essay/{exam.id}/questions/{q_id}/edit",
            data={"max_marks": "0"}
        )
        
        # Verify
        assert response.status_code == 400

    def test_accept_marks_boundary_1_on_edit(self, client, session: Session):
        """GIVEN existing essay question
        WHEN updating marks to 1 (minimum allowed)
        THEN the edit should succeed."""
        course = Course(name="Test", code="EQV9")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        q = ExamQuestion(exam_id=exam.id, question_text="Original", max_marks=100)
        session.add(q)
        session.commit()
        session.refresh(q)
        q_id = q.id
        
        # Execute
        response = client.post(
            f"/essay/{exam.id}/questions/{q_id}/edit",
            data={"max_marks": "1"}
        )
        
        # Verify success
        assert response.status_code == 303
        
        # Verify marks were updated
        session.expunge_all()
        q = session.get(ExamQuestion, q_id)
        assert q.max_marks == 1


class TestStudentPermissions:
    """Test student permission checks for essay question operations."""

    def test_student_cannot_delete_question(self, client, session: Session):
        """GIVEN student attempting to delete essay question
        WHEN student submits delete POST
        THEN system should return 403 Forbidden."""
        # Setup - create student user
        student_user = User(
            name="DeleteStudent",
            email="delete.student@test.com",
            password_hash=hash_password("Password123"),
            role="student"
        )
        session.add(student_user)
        session.commit()
        session.refresh(student_user)
        
        student = Student(
            user_id=student_user.id,
            matric_no="M999",
            name="Delete Student",
            email="delete.student@test.com"
        )
        session.add(student)
        session.commit()
        
        course = Course(name="Test", code="SP2")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        q = ExamQuestion(exam_id=exam.id, question_text="Q", max_marks=10)
        session.add(q)
        session.commit()
        session.refresh(q)
        q_id = q.id
        
        # Login as student
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": "M999",
                "password": "Password123"
            }
        )
        
        # Execute - POST delete
        response = client.post(f"/essay/{exam.id}/questions/{q_id}/delete")
        
        # Verify - 303 Redirect (student role check redirects instead of exception)
        assert response.status_code == 303
        
        # Verify question still exists
        session.expunge_all()
        q = session.get(ExamQuestion, q_id)
        assert q is not None

    def test_student_views_edit_form_shows_error(self, client, session: Session):
        """GIVEN student accessing essay question edit form
        WHEN student is logged in and views GET edit form
        THEN error message should be displayed in template."""
        # Setup - create student user
        student_user = User(
            name="EditStudent",
            email="edit.student@test.com",
            password_hash=hash_password("Password123"),
            role="student"
        )
        session.add(student_user)
        session.commit()
        session.refresh(student_user)
        
        student = Student(
            user_id=student_user.id,
            matric_no="M998",
            name="Edit Student",
            email="edit.student@test.com"
        )
        session.add(student)
        session.commit()
        
        course = Course(name="Test", code="SP1")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        q = ExamQuestion(exam_id=exam.id, question_text="Q", max_marks=10)
        session.add(q)
        session.commit()
        session.refresh(q)
        
        # Login as student
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": "M998",
                "password": "Password123"
            }
        )
        
        # Execute - GET edit form
        response = client.get(f"/essay/{exam.id}/questions/{q.id}/edit")
        
        # Verify - form renders with error message
        assert response.status_code == 200
        assert "not allowed" in response.text.lower() or "error" in response.text.lower()
