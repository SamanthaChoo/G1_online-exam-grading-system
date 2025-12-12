from datetime import datetime
from typing import List, Optional

from app.models import EssayAnswer, Exam, ExamAttempt, ExamQuestion
from app.utils import sanitize_question_text, sanitize_feedback, validate_marks
from sqlmodel import Session, select


def create_exam(session: Session, title: str, duration_minutes: int) -> Exam:
    exam = Exam(title=title, duration_minutes=duration_minutes)
    session.add(exam)
    session.commit()
    session.refresh(exam)
    return exam


def get_exam(session: Session, exam_id: int) -> Optional[Exam]:
    return session.get(Exam, exam_id)


def add_question(session: Session, exam_id: int, question_text: str, max_marks: int) -> ExamQuestion:
    # Ensure the target exam exists before adding the question
    exam = session.get(Exam, exam_id)
    if not exam:
        raise ValueError(f"Exam with id={exam_id} does not exist")

    # Sanitize question text to prevent XSS
    sanitized_text = sanitize_question_text(question_text)
    if not sanitized_text:
        raise ValueError("Question text cannot be empty after sanitization")

    # Validate max_marks is positive
    if max_marks < 1:
        raise ValueError("max_marks must be at least 1")
    if max_marks > 100:
        raise ValueError("max_marks cannot exceed 100")

    q = ExamQuestion(exam_id=exam_id, question_text=sanitized_text, max_marks=max_marks)
    session.add(q)
    session.commit()
    session.refresh(q)
    return q


def list_questions(session: Session, exam_id: int) -> List[ExamQuestion]:
    return session.exec(select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)).all()


def get_question(session: Session, question_id: int) -> Optional[ExamQuestion]:
    """Retrieve a single essay question by ID."""
    return session.get(ExamQuestion, question_id)


def edit_question(
    session: Session,
    question_id: int,
    question_text: Optional[str] = None,
    max_marks: Optional[int] = None,
) -> ExamQuestion:
    """Edit an existing essay question.

    Args:
        session: Database session
        question_id: ID of the question to edit
        question_text: New question text (optional)
        max_marks: New max marks (optional)

    Returns:
        Updated ExamQuestion

    Raises:
        ValueError: If question doesn't exist or validation fails
    """
    question = session.get(ExamQuestion, question_id)
    if not question:
        raise ValueError(f"Question with id={question_id} does not exist")

    if question_text is not None:
        sanitized_text = sanitize_question_text(question_text)
        if not sanitized_text:
            raise ValueError("Question text cannot be empty after sanitization")
        question.question_text = sanitized_text

    if max_marks is not None:
        if max_marks < 1:
            raise ValueError("max_marks must be at least 1")
        if max_marks > 100:
            raise ValueError("max_marks cannot exceed 100")
        question.max_marks = max_marks

    session.add(question)
    session.commit()
    session.refresh(question)
    return question


def delete_question(session: Session, question_id: int) -> None:
    """Delete an essay question and its associated answers.

    Args:
        session: Database session
        question_id: ID of the question to delete

    Raises:
        ValueError: If question doesn't exist
    """
    question = session.get(ExamQuestion, question_id)
    if not question:
        raise ValueError(f"Question with id={question_id} does not exist")

    # Delete the question (answers should cascade delete due to foreign key)
    session.delete(question)
    session.commit()


def _find_in_progress_attempt(session: Session, exam_id: int, student_id: int) -> Optional[ExamAttempt]:
    stmt = select(ExamAttempt).where(
        (ExamAttempt.exam_id == exam_id)
        & (ExamAttempt.student_id == student_id)
        & (ExamAttempt.status == "in_progress")
    )
    return session.exec(stmt).first()


def start_attempt(session: Session, exam_id: int, student_id: int) -> ExamAttempt:
    # Resume if exists
    attempt = _find_in_progress_attempt(session, exam_id, student_id)
    if attempt:
        return attempt

    # If there's already a final attempt (submitted/timed_out), do not create a new one.
    stmt_final = select(ExamAttempt).where(
        (ExamAttempt.exam_id == exam_id) & (ExamAttempt.student_id == student_id) & (ExamAttempt.is_final == 1)
    )
    final_attempt = session.exec(stmt_final).first()
    if final_attempt:
        # Return the existing final attempt — caller should handle redirect/notice.
        return final_attempt

    # Create a new attempt
    attempt = ExamAttempt(
        exam_id=exam_id,
        student_id=student_id,
        started_at=datetime.utcnow(),
        status="in_progress",
        is_final=0,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def submit_answers(session: Session, exam_id: int, student_id: int, answers: List[dict]) -> ExamAttempt:
    # find or create attempt
    attempt = _find_in_progress_attempt(session, exam_id, student_id)
    if not attempt:
        attempt = start_attempt(session, exam_id, student_id)

    # Upsert answers
    for a in answers:
        qid = a.get("question_id")
        text = a.get("answer_text")
        stmt = select(EssayAnswer).where((EssayAnswer.attempt_id == attempt.id) & (EssayAnswer.question_id == qid))
        existing = session.exec(stmt).first()
        if existing:
            existing.answer_text = text
            session.add(existing)
        else:
            new = EssayAnswer(attempt_id=attempt.id, question_id=qid, answer_text=text)
            session.add(new)
    # mark submitted
    attempt.status = "submitted"
    attempt.is_final = 1
    attempt.submitted_at = datetime.utcnow()
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def timeout_attempt(
    session: Session,
    exam_id: int,
    student_id: int,
    answers: Optional[List[dict]] = None,
) -> ExamAttempt:
    attempt = _find_in_progress_attempt(session, exam_id, student_id)
    if not attempt:
        attempt = start_attempt(session, exam_id, student_id)

    # Save partial answers if provided
    if answers:
        for a in answers:
            qid = a.get("question_id")
            text = a.get("answer_text")
            stmt = select(EssayAnswer).where((EssayAnswer.attempt_id == attempt.id) & (EssayAnswer.question_id == qid))
            existing = session.exec(stmt).first()
            if existing:
                existing.answer_text = text
                session.add(existing)
            else:
                new = EssayAnswer(attempt_id=attempt.id, question_id=qid, answer_text=text)
                session.add(new)

    attempt.status = "timed_out"
    attempt.is_final = 1
    attempt.submitted_at = datetime.utcnow()
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def edit_answer(
    session: Session,
    attempt_id: int,
    question_id: int,
    answer_text: Optional[str] = None,
) -> EssayAnswer:
    """Edit an existing essay answer during an in-progress attempt.

    Args:
        session: Database session
        attempt_id: ID of the attempt
        question_id: ID of the question
        answer_text: New answer text (optional)

    Returns:
        Updated EssayAnswer

    Raises:
        ValueError: If answer doesn't exist, attempt is final, or validation fails
    """
    # Check that attempt exists and is in_progress
    attempt = session.get(ExamAttempt, attempt_id)
    if not attempt:
        raise ValueError(f"Attempt with id={attempt_id} does not exist")

    if attempt.status != "in_progress":
        raise ValueError(
            f"Cannot edit answers for attempt with status '{attempt.status}'. "
            f"Only 'in_progress' attempts can be edited."
        )

    # Find the answer
    stmt = select(EssayAnswer).where(
        (EssayAnswer.attempt_id == attempt_id) & (EssayAnswer.question_id == question_id)
    )
    answer = session.exec(stmt).first()

    if not answer:
        raise ValueError(f"Answer for question {question_id} in attempt {attempt_id} does not exist")

    if answer_text is not None:
        answer.answer_text = answer_text

    session.add(answer)
    session.commit()
    session.refresh(answer)
    return answer


def grade_attempt(
    session: Session,
    attempt_id: int,
    scores: List[dict],
    feedback_list: Optional[List[dict]] = None,
) -> dict:
    """Grade an exam attempt with marks and optional feedback.

    Args:
        session: Database session
        attempt_id: ID of the attempt to grade
        scores: List of dicts with question_id and marks
        feedback_list: Optional list of dicts with question_id and feedback

    Returns:
        Dict with grading summary

    Raises:
        ValueError: If marks are out of valid range
    """
    # Build feedback map if provided
    feedback_map = {}
    if feedback_list:
        for f in feedback_list:
            qid = f.get("question_id")
            text = f.get("feedback", "")
            if text:
                feedback_map[qid] = sanitize_feedback(text)

    # Update marks_awarded for each question
    total = 0
    for s in scores:
        qid = s.get("question_id")
        marks = s.get("marks")

        # Get the question to check max_marks
        question = session.get(ExamQuestion, qid)
        if not question:
            raise ValueError(f"Question {qid} does not exist")

        # Validate marks are in range
        try:
            validate_marks(marks, question.max_marks)
        except ValueError as e:
            raise ValueError(f"Question {qid}: {str(e)}")

        stmt = select(EssayAnswer).where((EssayAnswer.attempt_id == attempt_id) & (EssayAnswer.question_id == qid))
        ans = session.exec(stmt).first()
        if ans:
            ans.marks_awarded = marks
            if qid in feedback_map:
                ans.grader_feedback = feedback_map[qid]
            session.add(ans)
            total += marks or 0
        else:
            # If no answer row exists yet, create one with marks_awarded
            new = EssayAnswer(
                attempt_id=attempt_id,
                question_id=qid,
                answer_text=None,
                marks_awarded=marks,
                grader_feedback=feedback_map.get(qid),
            )
            session.add(new)
            total += marks or 0
    session.commit()

    # Optionally compute total from table to ensure consistency
    stmt2 = select(EssayAnswer).where(EssayAnswer.attempt_id == attempt_id)
    answers = session.exec(stmt2).all()
    computed_total = sum((a.marks_awarded or 0) for a in answers)

    return {
        "attempt_id": attempt_id,
        "total_marks": computed_total,
        "answers_graded": len(answers),
    }
