"""Acceptance tests for essay question edit and delete features.

These tests verify:
- Editing essay question text and marks via POST to /essay/{exam_id}/questions/{q_id}/edit
- Deleting essay questions via POST to /essay/{exam_id}/questions/{q_id}/delete
- Validation of empty text and invalid marks
- Persistence of changes

Given-When-Then format used throughout.
"""

import pytest
from app.models import Exam, ExamQuestion, Course
from sqlmodel import Session, select


class TestEditEssayQuestion:
    """Tests for editing essay questions via /essay/{exam_id}/questions/{q_id}/edit endpoint."""

    def test_edit_question_text(self, client, session: Session):
        """GIVEN a question with text 'Original'
        WHEN updating question_text to 'Updated'
        THEN the question text should be updated in the database."""
        # Setup
        course = Course(name="Test Course 1", code="C1")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        q = ExamQuestion(exam_id=exam.id, question_text="Original", max_marks=10)
        session.add(q)
        session.commit()
        session.refresh(q)
        q_id = q.id
        
        # Execute - POST form data
        response = client.post(
            f"/essay/{exam.id}/questions/{q_id}/edit",
            data={"question_text": "Updated"}
        )
        assert response.status_code in [200, 303]  # 303 if redirects, 200 if returns form
        
        # Verify - fresh session query
        session.expunge_all()
        updated = session.get(ExamQuestion, q_id)
        assert updated is not None
        assert updated.question_text == "Updated"

    def test_edit_question_marks(self, client, session: Session):
        """GIVEN a question with max_marks=10
        WHEN updating max_marks to 20
        THEN the marks should be updated in the database."""
        course = Course(name="Test Course 2", code="C2")
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
        
        # Execute - POST form data with marks as string
        response = client.post(
            f"/essay/{exam.id}/questions/{q_id}/edit",
            data={"max_marks": "20"}
        )
        assert response.status_code in [200, 303]
        
        # Verify
        session.expunge_all()
        updated = session.get(ExamQuestion, q_id)
        assert updated is not None
        assert updated.max_marks == 20

    def test_persist_edited_question(self, client, session: Session):
        """GIVEN an edited question
        WHEN querying the database after the request
        THEN the changes should persist across sessions."""
        course = Course(name="Test Course 3", code="C3")
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
        
        # Execute
        response = client.post(
            f"/essay/{exam.id}/questions/{q_id}/edit",
            data={"question_text": "Changed"}
        )
        assert response.status_code in [200, 303]
        
        # Verify persistence
        session.expunge_all()
        reloaded = session.get(ExamQuestion, q_id)
        assert reloaded is not None
        assert reloaded.question_text == "Changed"

    def test_edit_both_text_and_marks(self, client, session: Session):
        """GIVEN a question with text 'Q' and max_marks=10
        WHEN updating both text to 'New Q' and marks to 25
        THEN both fields should be updated."""
        course = Course(name="Test Course 4", code="C4")
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
        
        # Execute - update both fields
        response = client.post(
            f"/essay/{exam.id}/questions/{q_id}/edit",
            data={"question_text": "New Q", "max_marks": "25"}
        )
        assert response.status_code in [200, 303]
        
        # Verify
        session.expunge_all()
        updated = session.get(ExamQuestion, q_id)
        assert updated is not None
        assert updated.question_text == "New Q"
        assert updated.max_marks == 25

    def test_reject_empty_text(self, client, session: Session):
        """GIVEN a question with valid text
        WHEN trying to update with empty text (whitespace only)
        THEN the request should be rejected with 400."""
        course = Course(name="Test Course 5", code="C5")
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
        
        # Execute - whitespace only gets sanitized to empty
        response = client.post(
            f"/essay/{exam.id}/questions/{q_id}/edit",
            data={"question_text": "   "}
        )
        
        # Verify - whitespace should be rejected
        assert response.status_code == 400

    def test_reject_zero_marks(self, client, session: Session):
        """GIVEN a question with valid marks
        WHEN trying to update with zero marks
        THEN the request should be rejected with 400."""
        course = Course(name="Test Course 6", code="C6")
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
        
        # Execute
        response = client.post(
            f"/essay/{exam.id}/questions/{q_id}/edit",
            data={"max_marks": "0"}
        )
        
        # Verify
        assert response.status_code == 400

    def test_reject_negative_marks(self, client, session: Session):
        """GIVEN a question with valid marks
        WHEN trying to update with negative marks
        THEN the request should be rejected with 400."""
        course = Course(name="Test Course 7", code="C7")
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
        
        # Execute
        response = client.post(
            f"/essay/{exam.id}/questions/{q_id}/edit",
            data={"max_marks": "-5"}
        )
        
        # Verify
        assert response.status_code == 400

    def test_edit_with_no_changes(self, client, session: Session):
        """GIVEN a question
        WHEN submitting edit form with no data changes
        THEN the question should remain unchanged."""
        course = Course(name="Test Course 8", code="C8")
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
        
        # Execute - empty form or only None values
        response = client.post(
            f"/essay/{exam.id}/questions/{q_id}/edit",
            data={}
        )
        assert response.status_code in [200, 303]
        
        # Verify unchanged
        session.expunge_all()
        unchanged = session.get(ExamQuestion, q_id)
        assert unchanged is not None
        assert unchanged.question_text == "Q"
        assert unchanged.max_marks == 10


class TestDeleteEssayQuestion:
    """Tests for deleting essay questions via /essay/{exam_id}/questions/{q_id}/delete endpoint."""

    def test_delete_question(self, client, session: Session):
        """GIVEN a question in the database
        WHEN deleting the question
        THEN the question should no longer exist."""
        course = Course(name="Test Course 9", code="C9")
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
        
        # Execute
        response = client.post(f"/essay/{exam.id}/questions/{q_id}/delete")
        assert response.status_code in [200, 303]
        
        # Verify
        session.expunge_all()
        deleted = session.get(ExamQuestion, q_id)
        assert deleted is None

    def test_delete_removes_from_list(self, client, session: Session):
        """GIVEN multiple questions in an exam
        WHEN deleting one question
        THEN the list of questions should no longer include it."""
        course = Course(name="Test Course 10", code="C10")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        q1 = ExamQuestion(exam_id=exam.id, question_text="Q1", max_marks=10)
        q2 = ExamQuestion(exam_id=exam.id, question_text="Q2", max_marks=15)
        session.add(q1)
        session.add(q2)
        session.commit()
        session.refresh(q1)
        session.refresh(q2)
        q1_id = q1.id
        q2_id = q2.id
        
        # Execute
        response = client.post(f"/essay/{exam.id}/questions/{q1_id}/delete")
        assert response.status_code in [200, 303]
        
        # Verify
        session.expunge_all()
        remaining = session.exec(
            select(ExamQuestion).where(ExamQuestion.exam_id == exam.id)
        ).all()
        assert len(remaining) == 1
        assert remaining[0].id == q2_id

    def test_delete_persisted(self, client, session: Session):
        """GIVEN a deleted question
        WHEN querying after deletion
        THEN the deletion should persist."""
        course = Course(name="Test Course 11", code="C11")
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
        
        # Execute
        response = client.post(f"/essay/{exam.id}/questions/{q_id}/delete")
        assert response.status_code in [200, 303]
        
        # Verify
        session.expunge_all()
        fresh_query = session.get(ExamQuestion, q_id)
        assert fresh_query is None

    def test_delete_updates_exam_structure(self, client, session: Session):
        """GIVEN an exam structure with questions
        WHEN deleting a question
        THEN the exam structure should be updated."""
        course = Course(name="Test Course 12", code="C12")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        q1 = ExamQuestion(exam_id=exam.id, question_text="Q1", max_marks=10)
        q2 = ExamQuestion(exam_id=exam.id, question_text="Q2", max_marks=15)
        session.add(q1)
        session.add(q2)
        session.commit()
        session.refresh(q1)
        session.refresh(q2)
        q1_id = q1.id
        
        # Execute
        response = client.post(f"/essay/{exam.id}/questions/{q1_id}/delete")
        assert response.status_code in [200, 303]
        
        # Verify structure updated
        session.expunge_all()
        remaining = session.exec(
            select(ExamQuestion).where(ExamQuestion.exam_id == exam.id)
        ).all()
        assert len(remaining) == 1

    def test_delete_nonexistent_returns_error(self, client, session: Session):
        """GIVEN a nonexistent question ID
        WHEN trying to delete it
        THEN the system should return 400."""
        course = Course(name="Test Course 13", code="C13")
        session.add(course)
        session.commit()
        session.refresh(course)
        
        exam = Exam(title="Exam", subject="Subj", course_id=course.id, duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        # Execute with nonexistent ID
        response = client.post(f"/essay/{exam.id}/questions/9999/delete")
        
        # Verify
        assert response.status_code == 400

    def test_delete_race_condition(self, client, session: Session):
        """GIVEN a deleted question
        WHEN attempting to delete it again
        THEN the system should handle gracefully."""
        course = Course(name="Test Course 14", code="C14")
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
        
        # Execute
        response1 = client.post(f"/essay/{exam.id}/questions/{q_id}/delete")
        assert response1.status_code in [200, 303]
        
        response2 = client.post(f"/essay/{exam.id}/questions/{q_id}/delete")
        
        # Verify
        assert response2.status_code == 400

    def test_delete_invalid_exam(self, client, session: Session):
        """GIVEN invalid exam and question IDs
        WHEN attempting to delete
        THEN the system should return error."""
        # Execute with nonexistent exam
        response = client.post(f"/essay/9999/questions/9999/delete")
        
        # Verify - may return 400 or 404 depending on implementation
        assert response.status_code in [400, 404]
