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


def add_question(
    session: Session, exam_id: int, question_text: str, max_marks: int, allow_negative_marks: bool = False
) -> ExamQuestion:
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
    if max_marks > 1000:
        raise ValueError("max_marks cannot exceed 1000")

    q = ExamQuestion(
        exam_id=exam_id,
        question_text=sanitized_text,
        max_marks=max_marks,
        allow_negative_marks=allow_negative_marks
    )
    session.add(q)
    session.commit()
    session.refresh(q)
    return q


def list_questions(session: Session, exam_id: int) -> List[ExamQuestion]:
    return session.exec(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
    ).all()


def _find_in_progress_attempt(
    session: Session, exam_id: int, student_id: int
) -> Optional[ExamAttempt]:
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
        (ExamAttempt.exam_id == exam_id)
        & (ExamAttempt.student_id == student_id)
        & (ExamAttempt.is_final == 1)
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


def submit_answers(
    session: Session, exam_id: int, student_id: int, answers: List[dict]
) -> ExamAttempt:
    # find or create attempt
    attempt = _find_in_progress_attempt(session, exam_id, student_id)
    if not attempt:
        attempt = start_attempt(session, exam_id, student_id)

    # Upsert answers
    for a in answers:
        qid = a.get("question_id")
        text = a.get("answer_text")
        stmt = select(EssayAnswer).where(
            (EssayAnswer.attempt_id == attempt.id) & (EssayAnswer.question_id == qid)
        )
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
            stmt = select(EssayAnswer).where(
                (EssayAnswer.attempt_id == attempt.id)
                & (EssayAnswer.question_id == qid)
            )
            existing = session.exec(stmt).first()
            if existing:
                existing.answer_text = text
                session.add(existing)
            else:
                new = EssayAnswer(
                    attempt_id=attempt.id, question_id=qid, answer_text=text
                )
                session.add(new)

    attempt.status = "timed_out"
    attempt.is_final = 1
    attempt.submitted_at = datetime.utcnow()
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def grade_attempt(
    session: Session,
    attempt_id: int,
    scores: List[dict],
    feedback_list: Optional[List[dict]] = None
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
        
        # Get the question to check max_marks and allow_negative_marks
        question = session.get(ExamQuestion, qid)
        if not question:
            raise ValueError(f"Question {qid} does not exist")
        
        # Validate marks are in range
        try:
            validate_marks(marks, question.max_marks, question.allow_negative_marks)
        except ValueError as e:
            raise ValueError(f"Question {qid}: {str(e)}")
        
        stmt = select(EssayAnswer).where(
            (EssayAnswer.attempt_id == attempt_id) & (EssayAnswer.question_id == qid)
        )
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
                grader_feedback=feedback_map.get(qid)
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
