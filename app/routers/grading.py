"""
Manual Grading Routes
Sprint 1 - User Story 2: Manual Grade Essay Questions

Handles:
- Listing students who submitted essays
- Viewing student submissions
- Awarding marks for essay questions
- Adding grader comments

Sprint 2 Enhancement:
- Bulk grading
- Rubric-based grading
- AI-assisted grading suggestions
- Grade moderation workflow
- Grade statistics and distribution
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func
from datetime import datetime

try:
    from app.database import get_session
    from app.models import Exam, EssayQuestion, EssaySubmission, ExamAttempt, Student
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from app.database import get_session
    from app.models import Exam, EssayQuestion, EssaySubmission, ExamAttempt, Student

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/{exam_id}/submissions")
def list_submissions(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    List all students who submitted for this exam.
    
    Sprint 1: Simple list with submission status
    Sprint 2: Add filtering, sorting, grading progress indicators
    
    Args:
        exam_id: Target exam ID
        request: FastAPI request object
        session: Database session
        
    Returns:
        Rendered template with student submission list
    """
    # Fetch exam
    exam = session.get(Exam, exam_id)
    if not exam:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Exam not found"}
        )
    
    # Get all attempts for this exam where submitted=True
    statement = select(ExamAttempt).where(
        ExamAttempt.exam_id == exam_id,
        ExamAttempt.submitted == True
    ).order_by(ExamAttempt.ended_at.desc())
    
    attempts = session.exec(statement).all()
    
    # Build submission data with student info and grading status
    submissions_data = []
    for attempt in attempts:
        # Get student info
        student = session.get(Student, attempt.student_id)
        
        # Count total questions
        stmt = select(func.count(EssayQuestion.id)).where(
            EssayQuestion.exam_id == exam_id
        )
        total_questions = session.exec(stmt).one()
        
        # Count graded questions (where marks_awarded is not None)
        stmt = select(func.count(EssaySubmission.id)).where(
            EssaySubmission.exam_id == exam_id,
            EssaySubmission.student_id == attempt.student_id,
            EssaySubmission.marks_awarded != None
        )
        graded_count = session.exec(stmt).one()
        
        # Calculate total marks awarded
        stmt = select(func.sum(EssaySubmission.marks_awarded)).where(
            EssaySubmission.exam_id == exam_id,
            EssaySubmission.student_id == attempt.student_id
        )
        total_marks = session.exec(stmt).one() or 0
        
        # Calculate max possible marks
        stmt = select(func.sum(EssayQuestion.max_marks)).where(
            EssayQuestion.exam_id == exam_id
        )
        max_marks = session.exec(stmt).one() or 0
        
        submissions_data.append({
            "student": student,
            "attempt": attempt,
            "total_questions": total_questions,
            "graded_count": graded_count,
            "is_fully_graded": graded_count == total_questions,
            "total_marks": total_marks,
            "max_marks": max_marks
        })
    
    return templates.TemplateResponse(
        "grading/list.html",
        {
            "request": request,
            "exam": exam,
            "submissions": submissions_data
        }
    )


@router.get("/{exam_id}/{student_id}")
def grade_student_submission(
    exam_id: int,
    student_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Display student's essay submissions for grading.
    
    Shows all essay questions with student answers and grading form.
    
    Sprint 1: Simple form for each question
    Sprint 2: Add rubric display, AI suggestions, comparison with model answers
    
    Args:
        exam_id: Target exam ID
        student_id: Student ID
        request: FastAPI request object
        session: Database session
        
    Returns:
        Rendered grading detail page
    """
    # Fetch exam and student
    exam = session.get(Exam, exam_id)
    student = session.get(Student, student_id)
    
    if not exam or not student:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "message": "Exam or Student not found"}
        )
    
    # Get all essay questions for this exam
    stmt = select(EssayQuestion).where(
        EssayQuestion.exam_id == exam_id
    ).order_by(EssayQuestion.id)
    questions = session.exec(stmt).all()
    
    # Get student's submissions
    submissions_dict = {}
    for question in questions:
        stmt = select(EssaySubmission).where(
            EssaySubmission.exam_id == exam_id,
            EssaySubmission.student_id == student_id,
            EssaySubmission.question_id == question.id
        )
        submission = session.exec(stmt).first()
        submissions_dict[question.id] = submission
    
    # Build grading data
    grading_data = []
    for question in questions:
        submission = submissions_dict.get(question.id)
        grading_data.append({
            "question": question,
            "submission": submission,
            "answer_text": submission.answer_text if submission else "No answer provided",
            "marks_awarded": submission.marks_awarded if submission else None,
            "grader_comments": submission.grader_comments if submission else None,
            "is_graded": submission and submission.marks_awarded is not None
        })
    
    return templates.TemplateResponse(
        "grading/detail.html",
        {
            "request": request,
            "exam": exam,
            "student": student,
            "grading_data": grading_data
        }
    )


@router.post("/{exam_id}/{student_id}")
async def save_grades(
    exam_id: int,
    student_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Save marks and comments for student's essay submissions.
    
    User Story 2: Manual Grade Essay Questions
    Processes grading form submission.
    
    Sprint 1: Simple mark assignment
    Sprint 2: Add validation, grade locking, audit trail
    
    Args:
        exam_id: Target exam ID
        student_id: Student ID
        request: FastAPI request object
        session: Database session
        
    Returns:
        Redirect to submissions list
    """
    form_data = await request.form()
    
    # Debug: print form data
    print(f"DEBUG: Form data keys: {list(form_data.keys())}")
    print(f"DEBUG: Form data: {dict(form_data)}")
    
    # Get all essay questions for this exam
    stmt = select(EssayQuestion).where(
        EssayQuestion.exam_id == exam_id
    )
    questions = session.exec(stmt).all()
    
    # Process grading for each question
    # Form fields: marks_{question_id}, comments_{question_id}
    for question in questions:
        marks_key = f"marks_{question.id}"
        comments_key = f"comments_{question.id}"
        
        marks_str = form_data.get(marks_key)
        comments = form_data.get(comments_key, "")
        
        # Skip if no marks provided or empty string
        if not marks_str or marks_str.strip() == "":
            continue
        
        try:
            marks_awarded = int(marks_str)
            
            # Validate marks range
            if marks_awarded < 0 or marks_awarded > question.max_marks:
                continue  # Skip invalid marks (Sprint 2: add error message)
            
            # Get submission
            stmt = select(EssaySubmission).where(
                EssaySubmission.exam_id == exam_id,
                EssaySubmission.student_id == student_id,
                EssaySubmission.question_id == question.id
            )
            submission = session.exec(stmt).first()
            
            if submission:
                # Update grading
                print(f"DEBUG: Updating submission {submission.id} with marks={marks_awarded}")
                submission.marks_awarded = marks_awarded
                submission.grader_comments = comments if comments else ""
                submission.graded_at = datetime.now()
                # Explicitly add to session and flush to see the UPDATE
                session.add(submission)
                session.flush()
                print(f"DEBUG: Updated submission {submission.id}")
            else:
                # This shouldn't happen (submission should exist)
                print(f"DEBUG: No submission found for question {question.id}")
                pass
                
        except (ValueError, TypeError) as e:
            # Skip invalid input
            print(f"DEBUG: Error processing question {question.id}: {e}")
            continue
    
    print("DEBUG: Committing changes...")
    session.commit()
    print("DEBUG: Changes committed")
    
    # Sprint 2: Add flash message "Grades saved successfully"
    return RedirectResponse(
        url=f"/grading/{exam_id}/submissions",
        status_code=303
    )
