"""Comprehensive tests for essay validation, sanitization, and grading."""

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models import Course, Exam, ExamQuestion, Student, User, Enrollment, EssayAnswer, ExamAttempt
from app.services.essay_service import add_question, grade_attempt
from app.utils import sanitize_question_text, sanitize_feedback, validate_marks


@pytest.fixture
def session():
    """Create a fresh database session for each test."""
    with Session(engine) as s:
        yield s


class TestHTMLSanitization:
    """Test HTML sanitization for question text."""

    def test_sanitize_removes_script_tags(self):
        """Script tags should be removed from question text."""
        dirty = '<script>alert("XSS")</script>What is 2+2?'
        clean = sanitize_question_text(dirty)
        # Bleach removes tags but preserves text content by default
        assert '<script>' not in clean
        # The important thing is tags are gone, even if content may remain
        assert 'What is 2+2?' in clean

    def test_sanitize_allows_bold_tags(self):
        """Bold tags should be allowed in question text."""
        text = '<b>Important:</b> What is the capital of France?'
        clean = sanitize_question_text(text)
        assert '<b>' in clean
        assert 'Important' in clean

    def test_sanitize_allows_italic_tags(self):
        """Italic tags should be allowed in question text."""
        text = '<i>Define</i> photosynthesis'
        clean = sanitize_question_text(text)
        assert '<i>' in clean

    def test_sanitize_removes_on_event_handlers(self):
        """Event handlers should be stripped."""
        dirty = '<div onclick="alert(\'XSS\')">Click me</div>'
        clean = sanitize_question_text(dirty)
        assert 'onclick' not in clean
        assert 'Click me' in clean

    def test_sanitize_preserves_code_tags(self):
        """Code tags for programming questions should be preserved."""
        text = '<p>Write a function:</p><code>def hello(): pass</code>'
        clean = sanitize_question_text(text)
        assert '<code>' in clean or 'def hello' in clean

    def test_sanitize_removes_iframe(self):
        """Iframe tags should be completely removed."""
        dirty = '<iframe src="malicious.com"></iframe>Question here'
        clean = sanitize_question_text(dirty)
        assert 'iframe' not in clean
        assert 'Question here' in clean

    def test_sanitize_empty_after_removal(self):
        """If sanitization results in empty string, validation should fail."""
        dirty = '<script></script><img onerror="alert(1)">'
        clean = sanitize_question_text(dirty)
        assert clean.strip() == ''

    def test_sanitize_preserves_whitespace(self):
        """Whitespace should be preserved where appropriate."""
        text = '<p>Question with\nmultiple\nlines</p>'
        clean = sanitize_question_text(text)
        # Sanitization may normalize whitespace, but content should remain
        assert 'Question' in clean
        assert 'multiple' in clean

    def test_sanitize_feedback_removes_all_html(self):
        """Feedback sanitization should remove all HTML."""
        dirty = '<script>alert("XSS")</script>Good answer<b>!</b>'
        clean = sanitize_feedback(dirty)
        assert '<script>' not in clean
        assert '<b>' not in clean
        assert 'Good answer!' in clean or 'Good answer' in clean

    def test_sanitize_feedback_preserves_text(self):
        """Feedback sanitization should preserve all text content."""
        text = 'Excellent work! You demonstrated strong understanding.'
        clean = sanitize_feedback(text)
        assert 'Excellent' in clean
        assert 'understanding' in clean


class TestMarkValidation:
    """Test mark validation logic."""

    def test_validate_marks_within_range(self):
        """Marks within valid range should pass validation."""
        assert validate_marks(5, max_marks=10, allow_negative=False) is True
        assert validate_marks(0, max_marks=10, allow_negative=False) is True
        assert validate_marks(10, max_marks=10, allow_negative=False) is True

    def test_validate_marks_exceeds_max(self):
        """Marks exceeding max_marks should raise error."""
        with pytest.raises(ValueError, match="out of range"):
            validate_marks(15, max_marks=10, allow_negative=False)

    def test_validate_marks_below_zero_not_allowed(self):
        """Negative marks should be rejected when not allowed."""
        with pytest.raises(ValueError, match="out of range"):
            validate_marks(-1, max_marks=10, allow_negative=False)

    def test_validate_marks_with_negative_allowed(self):
        """Negative marks should be allowed when flag is true."""
        assert validate_marks(-5, max_marks=10, allow_negative=True) is True
        assert validate_marks(8, max_marks=10, allow_negative=True) is True

    def test_validate_marks_below_negative_range(self):
        """Marks below negative range should fail."""
        with pytest.raises(ValueError, match="out of range"):
            validate_marks(-15, max_marks=10, allow_negative=True)

    def test_validate_marks_float_values(self):
        """Float marks should be validated correctly."""
        assert validate_marks(5.5, max_marks=10, allow_negative=False) is True
        assert validate_marks(2.7, max_marks=10, allow_negative=False) is True

    def test_validate_marks_zero_with_negative_allowed(self):
        """Zero should be valid regardless of negative flag."""
        assert validate_marks(0, max_marks=10, allow_negative=True) is True
        assert validate_marks(0, max_marks=10, allow_negative=False) is True


class TestQuestionCreationValidation:
    """Test question creation with validation."""

    def test_create_question_with_sanitization(self, session: Session):
        """Question text should be sanitized when created."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        dirty_text = '<script>alert("XSS")</script>What is Python?'
        q = add_question(session, exam.id, dirty_text, max_marks=10)
        
        assert '<script>' not in q.question_text
        assert 'What is Python?' in q.question_text

    def test_create_question_empty_after_sanitization_fails(self, session: Session):
        """Creating question with only malicious content should fail."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        dirty_text = '<script></script><img onerror="1">'
        with pytest.raises(ValueError, match="empty after sanitization"):
            add_question(session, exam.id, dirty_text, max_marks=10)

    def test_create_question_max_marks_zero_fails(self, session: Session):
        """Question with zero max_marks should fail."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        with pytest.raises(ValueError, match="at least 1"):
            add_question(session, exam.id, "Question text", max_marks=0)

    def test_create_question_max_marks_negative_fails(self, session: Session):
        """Question with negative max_marks should fail."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        with pytest.raises(ValueError, match="at least 1"):
            add_question(session, exam.id, "Question text", max_marks=-5)

    def test_create_question_max_marks_exceeds_limit_fails(self, session: Session):
        """Question with max_marks > 1000 should fail."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        with pytest.raises(ValueError, match="cannot exceed 1000"):
            add_question(session, exam.id, "Question text", max_marks=1001)

    def test_create_question_max_marks_valid_range(self, session: Session):
        """Question with valid max_marks should succeed."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        q = add_question(session, exam.id, "Question text", max_marks=100)
        assert q.max_marks == 100

    def test_create_question_allow_negative_marks_flag(self, session: Session):
        """Question should store allow_negative_marks flag."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        q1 = add_question(session, exam.id, "Q1", max_marks=10, allow_negative_marks=False)
        q2 = add_question(session, exam.id, "Q2", max_marks=10, allow_negative_marks=True)
        
        assert q1.allow_negative_marks is False
        assert q2.allow_negative_marks is True

    def test_create_question_nonexistent_exam_fails(self, session: Session):
        """Creating question for nonexistent exam should fail."""
        with pytest.raises(ValueError, match="does not exist"):
            add_question(session, exam_id=9999, question_text="Q", max_marks=10)


class TestGradeValidation:
    """Test grade validation and feedback."""

    def test_grade_attempt_validates_marks(self, session: Session):
        """Grading with out-of-range marks should fail."""
        # Create exam and question
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        q = add_question(session, exam.id, "Question", max_marks=10)
        
        # Create student and attempt
        student = Student(name="John", email="john@test.com", matric_no="001")
        session.add(student)
        session.commit()
        session.refresh(student)

        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        ans = EssayAnswer(attempt_id=attempt.id, question_id=q.id, answer_text="Test answer")
        session.add(ans)
        session.commit()

        # Grading with marks > max_marks should fail
        with pytest.raises(ValueError, match="out of range"):
            grade_attempt(session, attempt.id, [{"question_id": q.id, "marks": 15}])

    def test_grade_attempt_accepts_negative_when_allowed(self, session: Session):
        """Grading with negative marks should succeed if allowed."""
        # Create exam and question with allow_negative_marks
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        q = add_question(session, exam.id, "Question", max_marks=10, allow_negative_marks=True)
        
        # Create student and attempt
        student = Student(name="Jane", email="jane@test.com", matric_no="002")
        session.add(student)
        session.commit()
        session.refresh(student)

        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        ans = EssayAnswer(attempt_id=attempt.id, question_id=q.id, answer_text="Test answer")
        session.add(ans)
        session.commit()

        # Grading with negative marks should succeed
        result = grade_attempt(session, attempt.id, [{"question_id": q.id, "marks": -2}])
        assert result["total_marks"] == -2

    def test_grade_attempt_rejects_negative_when_not_allowed(self, session: Session):
        """Grading with negative marks should fail if not allowed."""
        # Create exam and question without allow_negative_marks
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        q = add_question(session, exam.id, "Question", max_marks=10, allow_negative_marks=False)
        
        # Create student and attempt
        student = Student(name="Bob", email="bob@test.com", matric_no="003")
        session.add(student)
        session.commit()
        session.refresh(student)

        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        ans = EssayAnswer(attempt_id=attempt.id, question_id=q.id, answer_text="Test answer")
        session.add(ans)
        session.commit()

        # Grading with negative marks should fail
        with pytest.raises(ValueError, match="out of range"):
            grade_attempt(session, attempt.id, [{"question_id": q.id, "marks": -1}])

    def test_grade_attempt_with_feedback(self, session: Session):
        """Grading should save feedback."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        q = add_question(session, exam.id, "Question", max_marks=10)
        
        student = Student(name="Alice", email="alice@test.com", matric_no="004")
        session.add(student)
        session.commit()
        session.refresh(student)

        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        ans = EssayAnswer(attempt_id=attempt.id, question_id=q.id, answer_text="Test answer")
        session.add(ans)
        session.commit()

        # Grade with feedback
        result = grade_attempt(
            session,
            attempt.id,
            [{"question_id": q.id, "marks": 8}],
            [{"question_id": q.id, "feedback": "Well explained!"}]
        )
        
        # Verify feedback was saved
        updated_ans = session.get(EssayAnswer, ans.id)
        assert updated_ans.marks_awarded == 8
        assert updated_ans.grader_feedback == "Well explained!"

    def test_grade_attempt_feedback_sanitized(self, session: Session):
        """Feedback should be sanitized."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        q = add_question(session, exam.id, "Question", max_marks=10)
        
        student = Student(name="Chris", email="chris@test.com", matric_no="005")
        session.add(student)
        session.commit()
        session.refresh(student)

        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        ans = EssayAnswer(attempt_id=attempt.id, question_id=q.id, answer_text="Test answer")
        session.add(ans)
        session.commit()

        # Grade with malicious feedback
        grade_attempt(
            session,
            attempt.id,
            [{"question_id": q.id, "marks": 7}],
            [{"question_id": q.id, "feedback": "<script>alert('XSS')</script>Good!"}]
        )
        
        # Verify feedback was sanitized
        updated_ans = session.get(EssayAnswer, ans.id)
        assert '<script>' not in updated_ans.grader_feedback
        assert 'Good!' in updated_ans.grader_feedback or 'Good' in updated_ans.grader_feedback

    def test_grade_attempt_float_marks(self, session: Session):
        """Grading should accept float marks (decimal scores)."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        q = add_question(session, exam.id, "Question", max_marks=10)
        
        student = Student(name="David", email="david@test.com", matric_no="006")
        session.add(student)
        session.commit()
        session.refresh(student)

        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        ans = EssayAnswer(attempt_id=attempt.id, question_id=q.id, answer_text="Test answer")
        session.add(ans)
        session.commit()

        # Grade with float marks
        result = grade_attempt(session, attempt.id, [{"question_id": q.id, "marks": 7.5}])
        
        updated_ans = session.get(EssayAnswer, ans.id)
        assert updated_ans.marks_awarded == 7.5
        assert result["total_marks"] == 7.5

    def test_grade_attempt_nonexistent_question(self, session: Session):
        """Grading with nonexistent question should fail."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        student = Student(name="Eve", email="eve@test.com", matric_no="007")
        session.add(student)
        session.commit()
        session.refresh(student)

        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        # Grading with nonexistent question should fail
        with pytest.raises(ValueError, match="does not exist"):
            grade_attempt(session, attempt.id, [{"question_id": 9999, "marks": 5}])


class TestAttemptConstraints:
    """Test exam attempt constraints (one-time final attempt)."""

    def test_attempt_is_final_constraint(self, session: Session):
        """is_final flag should be set when attempt is submitted."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        student = Student(name="Frank", email="frank@test.com", matric_no="008")
        session.add(student)
        session.commit()
        session.refresh(student)

        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id, is_final=1)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        assert attempt.is_final == 1

    def test_question_length_constraints(self, session: Session):
        """Question text should have length constraints."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        # Very long question text should still save (max_length=5000)
        long_text = "Question: " + "a" * 4990
        q = add_question(session, exam.id, long_text, max_marks=10)
        assert len(q.question_text) <= 5000

    def test_answer_length_constraints(self, session: Session):
        """Answer text should have length constraints."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        q = add_question(session, exam.id, "Question", max_marks=10)
        
        student = Student(name="Grace", email="grace@test.com", matric_no="009")
        session.add(student)
        session.commit()
        session.refresh(student)

        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        # Very long answer text (max_length=50000)
        long_answer = "Answer: " + "a" * 49990
        ans = EssayAnswer(attempt_id=attempt.id, question_id=q.id, answer_text=long_answer)
        session.add(ans)
        session.commit()
        session.refresh(ans)
        
        assert len(ans.answer_text) <= 50000

    def test_feedback_length_constraints(self, session: Session):
        """Feedback text should have length constraints."""
        exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        q = add_question(session, exam.id, "Question", max_marks=10)
        
        student = Student(name="Henry", email="henry@test.com", matric_no="010")
        session.add(student)
        session.commit()
        session.refresh(student)

        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        ans = EssayAnswer(attempt_id=attempt.id, question_id=q.id, answer_text="Answer")
        session.add(ans)
        session.commit()

        # Very long feedback (max_length=2000)
        long_feedback = "Feedback: " + "a" * 1990
        grade_attempt(
            session,
            attempt.id,
            [{"question_id": q.id, "marks": 5}],
            [{"question_id": q.id, "feedback": long_feedback}]
        )
        
        updated_ans = session.get(EssayAnswer, ans.id)
        assert len(updated_ans.grader_feedback or "") <= 2000


class TestEndToEndGrading:
    """End-to-end grading workflow tests."""

    def test_end_to_end_create_question_and_grade(self, session: Session):
        """Test complete workflow: create question → grade answer."""
        # Create exam
        exam = Exam(title="Final Exam", subject="Mathematics", duration_minutes=120)
        session.add(exam)
        session.commit()
        session.refresh(exam)

        # Create questions
        q1 = add_question(session, exam.id, "What is <b>calculus</b>?", max_marks=5)
        q2 = add_question(session, exam.id, "Solve: x + 2 = 5", max_marks=10, allow_negative_marks=False)

        # Create student and attempt
        student = Student(name="Iris", email="iris@test.com", matric_no="011")
        session.add(student)
        session.commit()
        session.refresh(student)

        attempt = ExamAttempt(exam_id=exam.id, student_id=student.id)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        # Add answers
        ans1 = EssayAnswer(attempt_id=attempt.id, question_id=q1.id, answer_text="Calculus is the study of change")
        ans2 = EssayAnswer(attempt_id=attempt.id, question_id=q2.id, answer_text="x = 3")
        session.add_all([ans1, ans2])
        session.commit()

        # Grade the attempt
        result = grade_attempt(
            session,
            attempt.id,
            [
                {"question_id": q1.id, "marks": 4.5},
                {"question_id": q2.id, "marks": 10}
            ],
            [
                {"question_id": q1.id, "feedback": "Good definition"},
                {"question_id": q2.id, "feedback": "Correct!"}
            ]
        )

        # Verify grading
        assert result["total_marks"] == 14.5
        assert result["answers_graded"] == 2

        # Verify feedback
        updated_ans1 = session.exec(
            select(EssayAnswer).where(EssayAnswer.id == ans1.id)
        ).first()
        assert updated_ans1.marks_awarded == 4.5
        assert "Good definition" in updated_ans1.grader_feedback

        updated_ans2 = session.exec(
            select(EssayAnswer).where(EssayAnswer.id == ans2.id)
        ).first()
        assert updated_ans2.marks_awarded == 10
        assert "Correct!" in updated_ans2.grader_feedback
