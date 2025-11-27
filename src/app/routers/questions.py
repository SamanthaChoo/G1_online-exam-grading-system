"""
MCQ Questions CRUD Router
Handles Create, Read, Update, Delete operations for MCQ questions

Routes:
- GET /questions/?exam_id=X - List all MCQ questions for an exam
- GET /questions/new?exam_id=X - Show form to create new question
- POST /questions/new?exam_id=X - Create new question
- GET /questions/{id} - View question details
- GET /questions/{id}/edit - Show form to edit question
- POST /questions/{id}/edit - Update question
- POST /questions/{id}/delete - Delete question
"""

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional
from pathlib import Path

from app.database import get_session
from app.models import MCQQuestion, Exam

# Get the project root directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


# Exam selection page for MCQ creation
@router.get("/select_exam", response_class=HTMLResponse)
def select_exam_for_mcq(request: Request, session: Session = Depends(get_session)):
    """
    Show a list of all exams to select before creating MCQ questions
    """
    exams = session.exec(select(Exam)).all()
    return templates.TemplateResponse(
        "questions/select_exam.html",
        {"request": request, "exams": exams}
    )


@router.get("/", response_class=HTMLResponse)
def list_questions(
    request: Request,
    exam_id: int,
    session: Session = Depends(get_session)
):
    """
    List all MCQ questions for a specific exam
    
    Args:
        exam_id: The exam ID to filter questions
    """
    # Get exam details
    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Get all questions for this exam
    statement = select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)
    questions = session.exec(statement).all()
    
    return templates.TemplateResponse(
        "questions/list.html",
        {
            "request": request,
            "exam": exam,
            "questions": questions
        }
    )


@router.get("/new", response_class=HTMLResponse)
def new_question_form(
    request: Request,
    exam_id: int,
    session: Session = Depends(get_session)
):
    """
    Show form to create a new MCQ question
    
    Args:
        exam_id: The exam ID for which to create question
    """
    # Get exam details
    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    return templates.TemplateResponse(
        "questions/form.html",
        {
            "request": request,
            "exam": exam,
            "question": None,  # No existing question for new form
            "action": "Create"
        }
    )


@router.post("/new")
def create_question(
    exam_id: int = Form(...),
    question_text: str = Form(...),
    option_a: str = Form(...),
    option_b: str = Form(...),
    option_c: str = Form(...),
    option_d: str = Form(...),
    correct_option: str = Form(...),
    explanation: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    """
    Create a new MCQ question
    
    Form fields:
        - exam_id: FK to exam
        - question_text: The question
        - option_a, option_b, option_c, option_d: Four options
        - correct_option: 'A', 'B', 'C', or 'D'
        - explanation: Optional explanation
    """
    # Validate correct_option
    if correct_option not in ['A', 'B', 'C', 'D']:
        raise HTTPException(status_code=400, detail="Correct option must be A, B, C, or D")
    
    # Create new question
    question = MCQQuestion(
        exam_id=exam_id,
        question_text=question_text,
        option_a=option_a,
        option_b=option_b,
        option_c=option_c,
        option_d=option_d,
        correct_option=correct_option,
        explanation=explanation if explanation else None
    )
    
    session.add(question)
    session.commit()
    session.refresh(question)
    
    # Redirect to questions list
    return RedirectResponse(
        url=f"/questions/?exam_id={exam_id}",
        status_code=303
    )


@router.get("/{question_id}", response_class=HTMLResponse)
def view_question(
    request: Request,
    question_id: int,
    session: Session = Depends(get_session)
):
    """
    View details of a specific question
    
    Args:
        question_id: The question ID to view
    """
    question = session.get(MCQQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Get exam details
    exam = session.get(Exam, question.exam_id)
    
    return templates.TemplateResponse(
        "questions/detail.html",
        {
            "request": request,
            "question": question,
            "exam": exam
        }
    )


@router.get("/{question_id}/edit", response_class=HTMLResponse)
def edit_question_form(
    request: Request,
    question_id: int,
    session: Session = Depends(get_session)
):
    """
    Show form to edit an existing MCQ question
    
    Args:
        question_id: The question ID to edit
    """
    question = session.get(MCQQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Get exam details
    exam = session.get(Exam, question.exam_id)
    
    return templates.TemplateResponse(
        "questions/form.html",
        {
            "request": request,
            "exam": exam,
            "question": question,
            "action": "Update"
        }
    )


@router.post("/{question_id}/edit")
def update_question(
    question_id: int,
    exam_id: int = Form(...),
    question_text: str = Form(...),
    option_a: str = Form(...),
    option_b: str = Form(...),
    option_c: str = Form(...),
    option_d: str = Form(...),
    correct_option: str = Form(...),
    explanation: Optional[str] = Form(None),
    session: Session = Depends(get_session)
):
    """
    Update an existing MCQ question
    
    Args:
        question_id: The question ID to update
        Form fields: Same as create_question
    """
    question = session.get(MCQQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Validate correct_option
    if correct_option not in ['A', 'B', 'C', 'D']:
        raise HTTPException(status_code=400, detail="Correct option must be A, B, C, or D")
    
    # Update question fields
    question.question_text = question_text
    question.option_a = option_a
    question.option_b = option_b
    question.option_c = option_c
    question.option_d = option_d
    question.correct_option = correct_option
    question.explanation = explanation if explanation else None
    
    session.add(question)
    session.commit()
    
    # Redirect to questions list
    return RedirectResponse(
        url=f"/questions/?exam_id={exam_id}",
        status_code=303
    )


@router.post("/{question_id}/delete")
def delete_question(
    question_id: int,
    session: Session = Depends(get_session)
):
    """
    Delete a question
    
    Args:
        question_id: The question ID to delete
    """
    question = session.get(MCQQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    exam_id = question.exam_id
    
    session.delete(question)
    session.commit()
    
    # Redirect to questions list
    return RedirectResponse(
        url=f"/questions/?exam_id={exam_id}",
        status_code=303
    )
