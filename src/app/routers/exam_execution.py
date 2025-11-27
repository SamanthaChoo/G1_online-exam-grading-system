"""
Exam Execution Router
Handles exam start, paper display, auto-save, and submission with auto-grading

Routes:
- GET /exam/start/{exam_id} - Exam start page with countdown timer
- GET /exam/paper/{exam_id} - Display exam paper with questions
- POST /exam/paper/{exam_id}/autosave - Auto-save student answers
- POST /exam/paper/{exam_id}/submit - Submit exam and perform auto-grading
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from datetime import datetime, timedelta
from typing import List, Dict
from pydantic import BaseModel
from pathlib import Path

from app.database import get_session
from app.models import Exam, MCQQuestion, StudentAnswer, ExamResult

# Get the project root directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


# Pydantic models for request/response
class AnswerData(BaseModel):
    question_id: int
    selected_option: str


class AutosaveRequest(BaseModel):
    student_id: int
    answers: List[AnswerData]


class SubmitRequest(BaseModel):
    student_id: int
    answers: List[AnswerData]


@router.get("/start/{exam_id}", response_class=HTMLResponse)
def exam_start_page(
    request: Request,
    exam_id: int,
    session: Session = Depends(get_session)
):
    """
    Exam start page with countdown timer
    
    Features:
    - Shows exam details
    - Displays countdown until exam start
    - Join Exam button appears 30 minutes before start
    - Button enabled only at start time
    
    Args:
        exam_id: The exam ID to start
    """
    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Calculate time differences
    now = datetime.utcnow()
    time_until_start = (exam.start_time - now).total_seconds()
    early_join_window = 30 * 60  # 30 minutes in seconds
    
    # Determine button state
    can_join = time_until_start <= early_join_window
    exam_started = time_until_start <= 0
    
    return templates.TemplateResponse(
        "exam_execution/start.html",
        {
            "request": request,
            "exam": exam,
            "can_join": can_join,
            "exam_started": exam_started,
            "time_until_start": int(time_until_start) if time_until_start > 0 else 0
        }
    )


@router.get("/paper/{exam_id}", response_class=HTMLResponse)
def exam_paper_page(
    request: Request,
    exam_id: int,
    student_id: int,  # Sprint 1: No auth, passed as query param
    session: Session = Depends(get_session)
):
    """
    Display exam paper with all MCQ questions
    
    Features:
    - Shows all questions with radio button options
    - Auto-saves answers every 60 seconds via JavaScript
    - Auto-submits when timer expires
    - Loads previously saved answers if student refreshes
    
    Args:
        exam_id: The exam ID
        student_id: Student ID (query param in Sprint 1)
    """
    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Get all questions for this exam
    statement = select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)
    questions = session.exec(statement).all()
    
    if not questions:
        raise HTTPException(status_code=404, detail="No questions found for this exam")
    
    # Get previously saved answers for this student
    answer_statement = select(StudentAnswer).where(
        StudentAnswer.exam_id == exam_id,
        StudentAnswer.student_id == student_id
    )
    saved_answers = session.exec(answer_statement).all()
    
    # Create a map of question_id -> selected_option
    answer_map = {ans.question_id: ans.selected_option for ans in saved_answers}
    
    # Calculate remaining time
    now = datetime.utcnow()
    elapsed_seconds = (now - exam.start_time).total_seconds()
    remaining_seconds = max(0, (exam.duration_minutes * 60) - elapsed_seconds)
    
    return templates.TemplateResponse(
        "exam_execution/paper.html",
        {
            "request": request,
            "exam": exam,
            "questions": questions,
            "student_id": student_id,
            "answer_map": answer_map,
            "remaining_seconds": int(remaining_seconds)
        }
    )


@router.post("/paper/{exam_id}/autosave")
async def autosave_answers(
    exam_id: int,
    data: AutosaveRequest,
    session: Session = Depends(get_session)
):
    """
    Auto-save student answers (called every 60 seconds via JavaScript)
    
    Features:
    - Upserts answers (update if exists, insert if new)
    - Updates timestamp on each save
    
    Args:
        exam_id: The exam ID
        data: Student ID and list of answers
    """
    try:
        for answer_data in data.answers:
            # Check if answer already exists
            statement = select(StudentAnswer).where(
                StudentAnswer.exam_id == exam_id,
                StudentAnswer.student_id == data.student_id,
                StudentAnswer.question_id == answer_data.question_id
            )
            existing_answer = session.exec(statement).first()
            
            if existing_answer:
                # Update existing answer
                existing_answer.selected_option = answer_data.selected_option
                existing_answer.updated_at = datetime.utcnow()
            else:
                # Create new answer
                new_answer = StudentAnswer(
                    student_id=data.student_id,
                    exam_id=exam_id,
                    question_id=answer_data.question_id,
                    selected_option=answer_data.selected_option
                )
                session.add(new_answer)
        
        session.commit()
        
        return JSONResponse(
            content={"status": "success", "message": "Answers saved"},
            status_code=200
        )
    
    except Exception as e:
        session.rollback()
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500
        )


@router.post("/paper/{exam_id}/submit")
async def submit_exam(
    exam_id: int,
    data: SubmitRequest,
    session: Session = Depends(get_session)
):
    """
    Submit exam and perform auto-grading
    
    Features:
    - Saves final answers
    - Compares answers with correct_option
    - Calculates score
    - Stores result in ExamResult table
    - Returns score and redirect URL
    
    Args:
        exam_id: The exam ID
        data: Student ID and list of answers
    """
    try:
        # Save final answers (similar to autosave)
        for answer_data in data.answers:
            statement = select(StudentAnswer).where(
                StudentAnswer.exam_id == exam_id,
                StudentAnswer.student_id == data.student_id,
                StudentAnswer.question_id == answer_data.question_id
            )
            existing_answer = session.exec(statement).first()
            
            if existing_answer:
                existing_answer.selected_option = answer_data.selected_option
                existing_answer.updated_at = datetime.utcnow()
            else:
                new_answer = StudentAnswer(
                    student_id=data.student_id,
                    exam_id=exam_id,
                    question_id=answer_data.question_id,
                    selected_option=answer_data.selected_option
                )
                session.add(new_answer)
        
        session.commit()
        
        # Perform auto-grading
        score_data = calculate_score(exam_id, data.student_id, session)
        
        # Save exam result
        result = ExamResult(
            student_id=data.student_id,
            exam_id=exam_id,
            score=score_data["score"],
            total_questions=score_data["total_questions"],
            correct_answers=score_data["correct_answers"]
        )
        session.add(result)
        session.commit()
        session.refresh(result)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "Exam submitted successfully",
                "result_id": result.id,
                "score": score_data["score"],
                "correct_answers": score_data["correct_answers"],
                "total_questions": score_data["total_questions"]
            },
            status_code=200
        )
    
    except Exception as e:
        session.rollback()
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500
        )


@router.get("/submitted/{exam_id}", response_class=HTMLResponse)
def exam_submitted_page(
    request: Request,
    exam_id: int,
    student_id: int,
    session: Session = Depends(get_session)
):
    """
    Show exam submitted confirmation with score
    
    Args:
        exam_id: The exam ID
        student_id: Student ID (query param)
    """
    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Get latest exam result for this student
    statement = select(ExamResult).where(
        ExamResult.exam_id == exam_id,
        ExamResult.student_id == student_id
    ).order_by(ExamResult.submitted_at.desc())
    
    result = session.exec(statement).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Exam result not found")
    
    return templates.TemplateResponse(
        "exam_execution/submitted.html",
        {
            "request": request,
            "exam": exam,
            "result": result
        }
    )


def calculate_score(exam_id: int, student_id: int, session: Session) -> Dict:
    """
    Auto-grading function
    Compares student answers with correct answers
    
    Args:
        exam_id: The exam ID
        student_id: The student ID
        session: Database session
    
    Returns:
        Dict with score, total_questions, and correct_answers
    """
    # Get all questions for this exam
    questions_statement = select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)
    questions = session.exec(questions_statement).all()
    
    # Get student's answers
    answers_statement = select(StudentAnswer).where(
        StudentAnswer.exam_id == exam_id,
        StudentAnswer.student_id == student_id
    )
    answers = session.exec(answers_statement).all()
    
    # Create answer map
    answer_map = {ans.question_id: ans.selected_option for ans in answers}
    
    # Calculate score
    total_questions = len(questions)
    correct_answers = 0
    
    for question in questions:
        student_answer = answer_map.get(question.id, "")
        if student_answer == question.correct_option:
            correct_answers += 1
    
    # Calculate percentage
    score = (correct_answers / total_questions * 100) if total_questions > 0 else 0
    
    return {
        "score": round(score, 2),
        "total_questions": total_questions,
        "correct_answers": correct_answers
    }
