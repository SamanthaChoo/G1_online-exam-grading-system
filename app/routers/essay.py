"""
Essay Question Management Routes
Sprint 1 - User Story 1: Create Essay Questions

Handles:
- Adding essay questions to exams
- Viewing essay questions for an exam
- Listing all essay questions

Sprint 2 Enhancement:
- Add question editing/deletion
- Bulk import from file
- Question bank/templates
- Authentication & authorization (lecturer role required)
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from datetime import datetime

try:
    from app.database import get_session
    from app.models import EssayQuestion, Exam
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from app.database import get_session
    from app.models import EssayQuestion, Exam

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/{exam_id}/add")
def add_essay_question_form(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Display form to add essay question to exam.
    
    Sprint 1: No authentication
    Sprint 2: Require lecturer role authentication
    
    Args:
        exam_id: Target exam ID
        request: FastAPI request object
        session: Database session
        
    Returns:
        Rendered template with form
    """
    # Fetch exam details
    exam = session.get(Exam, exam_id)
    
    if not exam:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Exam not found"}
        )
    
    return templates.TemplateResponse(
        "essays/add.html",
        {
            "request": request,
            "exam": exam
        }
    )


@router.post("/{exam_id}/add")
def add_essay_question(
    exam_id: int,
    question_text: str = Form(...),
    max_marks: int = Form(...),
    session: Session = Depends(get_session)
):
    """
    Handle essay question creation.
    
    Sprint 1: Direct insertion
    Sprint 2: Add validation, duplicate detection, batch import
    
    Args:
        exam_id: Target exam ID
        question_text: Essay question content
        max_marks: Maximum marks for question
        session: Database session
        
    Returns:
        Redirect to exam detail page
    """
    # Validate exam exists
    exam = session.get(Exam, exam_id)
    if not exam:
        return RedirectResponse(url="/exams", status_code=303)
    
    # Create essay question
    essay_question = EssayQuestion(
        exam_id=exam_id,
        question_text=question_text,
        max_marks=max_marks
    )
    
    session.add(essay_question)
    session.commit()
    
    # Sprint 2: Add flash message support
    return RedirectResponse(
        url=f"/essays/{exam_id}/view",
        status_code=303
    )


@router.get("/{exam_id}/view")
def view_essay_questions(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    List all essay questions for an exam.
    
    Sprint 1: Simple list view
    Sprint 2: Add filtering, sorting, search, question statistics
    
    Args:
        exam_id: Target exam ID
        request: FastAPI request object
        session: Database session
        
    Returns:
        Rendered template with question list
    """
    # Fetch exam
    exam = session.get(Exam, exam_id)
    if not exam:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Exam not found"}
        )
    
    # Fetch all essay questions for this exam
    statement = select(EssayQuestion).where(
        EssayQuestion.exam_id == exam_id
    ).order_by(EssayQuestion.created_at)
    
    questions = session.exec(statement).all()
    
    return templates.TemplateResponse(
        "essays/list.html",
        {
            "request": request,
            "exam": exam,
            "questions": questions
        }
    )
