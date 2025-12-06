"""API endpoints for essay-based exams.

This router implements endpoints requested in Commit 1 (no validation / no error handling).
"""

from typing import List, Optional

from app.database import get_session
from app.services.essay_service import (
    add_question,
    create_exam,
    get_exam,
    grade_attempt,
    list_questions,
    start_attempt,
    submit_answers,
    timeout_attempt,
    _find_in_progress_attempt,
)
from app.models import EssayAnswer
from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select

router = APIRouter()


# --- Request/Response schemas (minimal, no validation) ---


class CreateExamIn(BaseModel):
    exam_title: str
    duration_minutes: int


class CreateQuestionIn(BaseModel):
    question_text: str
    max_marks: int


class AnswerIn(BaseModel):
    question_id: int
    answer_text: Optional[str] = None


class GradeIn(BaseModel):
    scores: List[dict]


# 1) EXAM CREATION
@router.post("/exam")
def api_create_exam(payload: CreateExamIn = Body(...), session: Session = Depends(get_session)):
    exam = create_exam(session, title=payload.exam_title, duration_minutes=payload.duration_minutes)
    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "duration_minutes": exam.duration_minutes,
    }


@router.get("/exam/{exam_id}")
def api_get_exam(exam_id: int, session: Session = Depends(get_session)):
    exam = get_exam(session, exam_id)
    # Minimal JSON
    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "duration_minutes": exam.duration_minutes,
        "start_time": exam.start_time,
        "end_time": exam.end_time,
    }


# 2) ADD ESSAY QUESTIONS
@router.post("/exam/{exam_id}/questions")
def api_add_question(
    exam_id: int,
    payload: CreateQuestionIn = Body(...),
    session: Session = Depends(get_session),
):
    q = add_question(
        session,
        exam_id=exam_id,
        question_text=payload.question_text,
        max_marks=payload.max_marks,
    )
    return {
        "question_id": q.id,
        "exam_id": q.exam_id,
        "question_text": q.question_text,
        "max_marks": q.max_marks,
    }


@router.get("/exam/{exam_id}/questions")
def api_list_questions(exam_id: int, session: Session = Depends(get_session)):
    qs = list_questions(session, exam_id)
    return [
        {
            "question_id": q.id,
            "question_text": q.question_text,
            "max_marks": q.max_marks,
        }
        for q in qs
    ]


# 3) START EXAM + ATTEMPT TRACKING
@router.post("/exam/{exam_id}/start")
def api_start_exam(exam_id: int, student_id: int = Query(...), session: Session = Depends(get_session)):
    attempt = start_attempt(session, exam_id, student_id)
    return {
        "attempt_id": attempt.id,
        "exam_id": attempt.exam_id,
        "student_id": attempt.student_id,
        "started_at": attempt.started_at,
        "status": attempt.status,
    }


# 4) SUBMIT ANSWERS
class SubmitPayload(BaseModel):
    answers: List[AnswerIn]


@router.post("/exam/{exam_id}/submit")
def api_submit(
    exam_id: int,
    student_id: int = Query(...),
    payload: SubmitPayload = Body(...),
    session: Session = Depends(get_session),
):
    answers = [a.dict() for a in payload.answers]
    attempt = submit_answers(session, exam_id, student_id, answers)
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "submitted_at": attempt.submitted_at,
    }


# 4.5) AUTO-SAVE ANSWERS (periodic save without submission)
class AutoSavePayload(BaseModel):
    answers: List[AnswerIn]


@router.post("/exam/{exam_id}/autosave")
def api_autosave(
    exam_id: int,
    student_id: int = Query(...),
    payload: AutoSavePayload = Body(...),
    session: Session = Depends(get_session),
):
    """Auto-save essay answers without submitting the attempt."""
    # Find or create an in-progress attempt
    attempt = _find_in_progress_attempt(session, exam_id, student_id)
    if not attempt:
        attempt = start_attempt(session, exam_id, student_id)

    # Upsert answers without changing attempt status
    for a in payload.answers:
        qid = a.question_id
        text = a.answer_text
        stmt = select(EssayAnswer).where((EssayAnswer.attempt_id == attempt.id) & (EssayAnswer.question_id == qid))
        existing = session.exec(stmt).first()
        if existing:
            existing.answer_text = text
            session.add(existing)
        else:
            new = EssayAnswer(attempt_id=attempt.id, question_id=qid, answer_text=text)
            session.add(new)

    session.commit()
    return {"status": "success", "attempt_id": attempt.id}


# 5) AUTO-SUBMIT ON TIMEOUT
class TimeoutPayload(BaseModel):
    answers: Optional[List[AnswerIn]] = None


@router.post("/exam/{exam_id}/timeout")
def api_timeout(
    exam_id: int,
    student_id: int = Query(...),
    payload: TimeoutPayload = Body(None),
    session: Session = Depends(get_session),
):
    answers = [a.dict() for a in payload.answers] if payload and payload.answers else None
    attempt = timeout_attempt(session, exam_id, student_id, answers)
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "submitted_at": attempt.submitted_at,
    }


# 6) MANUAL GRADING
class ScoresIn(BaseModel):
    scores: List[dict]


@router.post("/exam/{exam_id}/grade/{attempt_id}")
def api_grade(
    exam_id: int,
    attempt_id: int,
    payload: ScoresIn = Body(...),
    session: Session = Depends(get_session),
):
    result = grade_attempt(session, attempt_id, payload.scores)
    return result
