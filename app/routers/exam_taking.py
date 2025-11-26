"""
Exam Taking Routes
Sprint 1 - User Stories 3 & 4:
- Auto Submit When Time Ends
- One Attempt Enforcement

Handles:
- Starting exam (with attempt tracking)
- Taking exam (with countdown timer)
- Manual submission
- Auto-submission when time expires
- Preventing multiple attempts

Sprint 2 Enhancement:
- Add pause/resume functionality
- Save draft answers
- Browser tab monitoring
- Proctoring integration
"""

from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from datetime import datetime, timedelta
from typing import List

try:
    from app.database import get_session
    from app.models import Exam, ExamAttempt, EssayQuestion, EssaySubmission
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from app.database import get_session
    from app.models import Exam, ExamAttempt, EssayQuestion, EssaySubmission

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/{exam_id}/start")
def start_exam(
    exam_id: int,
    student_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Start exam or show attempt status.
    
    User Story 4: One Attempt Enforcement
    - Checks if student already attempted
    - Prevents retake if submitted or auto-submitted
    
    Sprint 1: student_id from query parameter
    Sprint 2: Get student_id from authenticated session
    
    Args:
        exam_id: Target exam ID
        student_id: Student ID (from query param in Sprint 1)
        request: FastAPI request object
        session: Database session
        
    Returns:
        Exam taking page OR attempt status page
    """
    # Fetch exam
    exam = session.get(Exam, exam_id)
    if not exam:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Exam not found"}
        )
    
    # Check for existing attempt
    statement = select(ExamAttempt).where(
        ExamAttempt.exam_id == exam_id,
        ExamAttempt.student_id == student_id
    )
    existing_attempt = session.exec(statement).first()
    
    # User Story 4: Enforce one attempt rule
    if existing_attempt:
        if existing_attempt.submitted and not existing_attempt.auto_submitted:
            # Student manually submitted
            return templates.TemplateResponse(
                "exams/already_attempted.html",
                {
                    "request": request,
                    "exam": exam,
                    "attempt": existing_attempt
                }
            )
        elif existing_attempt.auto_submitted:
            # Time expired - auto submitted
            return templates.TemplateResponse(
                "exams/auto_submitted.html",
                {
                    "request": request,
                    "exam": exam,
                    "attempt": existing_attempt
                }
            )
        else:
            # Attempt exists but not submitted (page refresh during exam)
            # Continue with existing attempt
            pass
    else:
        # Create new attempt
        existing_attempt = ExamAttempt(
            exam_id=exam_id,
            student_id=student_id,
            started_at=datetime.now()
        )
        session.add(existing_attempt)
        session.commit()
        session.refresh(existing_attempt)
    
    # Fetch essay questions
    statement = select(EssayQuestion).where(
        EssayQuestion.exam_id == exam_id
    ).order_by(EssayQuestion.id)
    questions = session.exec(statement).all()
    
    # Calculate remaining time
    elapsed = (datetime.now() - existing_attempt.started_at).total_seconds()
    total_seconds = exam.duration_minutes * 60
    remaining_seconds = max(0, int(total_seconds - elapsed))
    
    # User Story 3: Auto-submit if time already expired
    if remaining_seconds == 0 and not existing_attempt.submitted:
        return _auto_submit_exam(exam_id, student_id, session, request)
    
    return templates.TemplateResponse(
        "exams/take.html",
        {
            "request": request,
            "exam": exam,
            "questions": questions,
            "student_id": student_id,
            "remaining_seconds": remaining_seconds,
            "attempt": existing_attempt
        }
    )


@router.post("/{exam_id}/submit")
async def submit_exam(
    exam_id: int,
    student_id: int = Form(...),
    request: Request = None,
    session: Session = Depends(get_session)
):
    """
    Handle manual exam submission by student.
    
    Saves all essay answers and marks attempt as submitted.
    
    Sprint 1: Accept answers as form data
    Sprint 2: Add validation, incomplete submission warnings
    
    Args:
        exam_id: Target exam ID
        student_id: Student ID (from form)
        request: FastAPI request object
        session: Database session
        
    Returns:
        Redirect to confirmation page
    """
    # Get exam and attempt
    exam = session.get(Exam, exam_id)
    statement = select(ExamAttempt).where(
        ExamAttempt.exam_id == exam_id,
        ExamAttempt.student_id == student_id
    )
    attempt = session.exec(statement).first()
    
    if not attempt or attempt.submitted:
        return RedirectResponse(url="/", status_code=303)
    
    # Get all essay questions
    statement = select(EssayQuestion).where(
        EssayQuestion.exam_id == exam_id
    )
    questions = session.exec(statement).all()
    
    # Save essay submissions
    # Sprint 1: Collect answers from form fields named "answer_{question_id}"
    if request:
        form_data = await request.form()
        for question in questions:
            answer_key = f"answer_{question.id}"
            answer_text = form_data.get(answer_key, "")
            
            # Check if submission already exists
            stmt = select(EssaySubmission).where(
                EssaySubmission.exam_id == exam_id,
                EssaySubmission.student_id == student_id,
                EssaySubmission.question_id == question.id
            )
            existing = session.exec(stmt).first()
            
            if existing:
                # Update existing
                existing.answer_text = answer_text
                existing.submitted_at = datetime.now()
            else:
                # Create new
                submission = EssaySubmission(
                    exam_id=exam_id,
                    student_id=student_id,
                    question_id=question.id,
                    answer_text=answer_text,
                    submitted_at=datetime.now()
                )
                session.add(submission)
    
    # Mark attempt as submitted
    attempt.submitted = True
    attempt.ended_at = datetime.now()
    
    session.commit()
    
    return RedirectResponse(
        url=f"/exam/{exam_id}/confirmation?student_id={student_id}",
        status_code=303
    )


@router.post("/{exam_id}/auto-submit")
async def auto_submit_exam(
    exam_id: int,
    student_id: int = Form(...),
    session: Session = Depends(get_session)
):
    """
    Handle auto-submission when timer expires.
    
    User Story 3: Auto Submit When Time Ends
    Called by JavaScript when countdown reaches 0.
    
    Sprint 1: Simple auto-save and mark as auto-submitted
    Sprint 2: Add grace period, notification to lecturer
    
    Args:
        exam_id: Target exam ID
        student_id: Student ID
        session: Database session
        
    Returns:
        JSON response for JavaScript handler
    """
    # Get attempt
    statement = select(ExamAttempt).where(
        ExamAttempt.exam_id == exam_id,
        ExamAttempt.student_id == student_id
    )
    attempt = session.exec(statement).first()
    
    if not attempt or attempt.submitted:
        return JSONResponse(
            {"status": "error", "message": "Invalid attempt"},
            status_code=400
        )
    
    # Ensure there is a submission row for each essay question
    questions_stmt = select(EssayQuestion).where(EssayQuestion.exam_id == exam_id)
    questions = session.exec(questions_stmt).all()

    for q in questions:
        existing_stmt = select(EssaySubmission).where(
            EssaySubmission.exam_id == exam_id,
            EssaySubmission.student_id == student_id,
            EssaySubmission.question_id == q.id
        )
        sub = session.exec(existing_stmt).first()
        if not sub:
            # Create an empty submission so grading works even if the student didn't type
            sub = EssaySubmission(
                exam_id=exam_id,
                student_id=student_id,
                question_id=q.id,
                answer_text="",
                submitted_at=datetime.now(),
                marks_awarded=None,
                graded_at=None,
                grader_comments=None,
            )
            session.add(sub)

    # Mark as auto-submitted
    attempt.submitted = True
    attempt.auto_submitted = True
    attempt.ended_at = datetime.now()
    
    session.commit()
    
    return JSONResponse({
        "status": "success",
        "message": "Exam auto-submitted due to time expiry",
        "redirect_url": f"/exam/{exam_id}/auto-submitted?student_id={student_id}"
    })


def _auto_submit_exam(exam_id: int, student_id: int, session: Session, request: Request):
    """
    Internal helper to auto-submit exam when time expires.
    Used when student tries to access exam after time expired.
    """
    statement = select(ExamAttempt).where(
        ExamAttempt.exam_id == exam_id,
        ExamAttempt.student_id == student_id
    )
    attempt = session.exec(statement).first()
    


def _reset_attempts_internal(session: Session, exam_id: int, student_id: int | None):
    # Delete submissions
    if student_id is not None:
        subs = session.exec(
            select(EssaySubmission).where(
                EssaySubmission.exam_id == exam_id,
                EssaySubmission.student_id == student_id
            )
        ).all()
        for s in subs:
            session.delete(s)
    else:
        subs = session.exec(
            select(EssaySubmission).where(EssaySubmission.exam_id == exam_id)
        ).all()
        for s in subs:
            session.delete(s)

    # Delete attempts
    if student_id is not None:
        attempts = session.exec(
            select(ExamAttempt).where(
                ExamAttempt.exam_id == exam_id,
                ExamAttempt.student_id == student_id
            )
        ).all()
        for a in attempts:
            session.delete(a)
    else:
        attempts = session.exec(
            select(ExamAttempt).where(ExamAttempt.exam_id == exam_id)
        ).all()
        for a in attempts:
            session.delete(a)


@router.post("/{exam_id}/reset-attempts")
def reset_attempts_post(
    exam_id: int,
    student_id: int | None = Form(None),
    session: Session = Depends(get_session)
):
    """TESTING-ONLY: Reset attempts and submissions via POST form."""
    _reset_attempts_internal(session, exam_id, student_id)
    session.commit()
    return JSONResponse({"status": "success", "message": "Attempts and submissions reset"})


@router.get("/{exam_id}/reset-attempts")
def reset_attempts_get(
    exam_id: int,
    student_id: int | None = Query(default=None),
    session: Session = Depends(get_session)
):
    """TESTING-ONLY: Reset attempts and submissions via GET with query param."""
    _reset_attempts_internal(session, exam_id, student_id)
    session.commit()
    return JSONResponse({"status": "success", "message": "Attempts and submissions reset"})
    if attempt and not attempt.submitted:
        attempt.submitted = True
        attempt.auto_submitted = True
        attempt.ended_at = datetime.now()
        session.commit()
    
    exam = session.get(Exam, exam_id)
    return templates.TemplateResponse(
        "exams/auto_submitted.html",
        {
            "request": request,
            "exam": exam,
            "attempt": attempt
        }
    )


@router.get("/{exam_id}/confirmation")
def exam_confirmation(
    exam_id: int,
    student_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Display submission confirmation page.
    
    Args:
        exam_id: Target exam ID
        student_id: Student ID
        request: FastAPI request object
        session: Database session
        
    Returns:
        Confirmation page
    """
    exam = session.get(Exam, exam_id)
    statement = select(ExamAttempt).where(
        ExamAttempt.exam_id == exam_id,
        ExamAttempt.student_id == student_id
    )
    attempt = session.exec(statement).first()
    
    return templates.TemplateResponse(
        "exams/confirmation.html",
        {
            "request": request,
            "exam": exam,
            "attempt": attempt,
            "student_id": student_id
        }
    )


@router.get("/{exam_id}/auto-submitted")
def auto_submitted_page(
    exam_id: int,
    student_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Display auto-submission confirmation page when timer expires.
    
    Args:
        exam_id: Target exam ID
        student_id: Student ID
        request: FastAPI request object
        session: Database session
        
    Returns:
        Auto-submitted confirmation page
    """
    exam = session.get(Exam, exam_id)
    statement = select(ExamAttempt).where(
        ExamAttempt.exam_id == exam_id,
        ExamAttempt.student_id == student_id
    )
    attempt = session.exec(statement).first()
    
    return templates.TemplateResponse(
        "exams/auto_submitted.html",
        {
            "request": request,
            "exam": exam,
            "attempt": attempt,
            "student_id": student_id
        }
    )
