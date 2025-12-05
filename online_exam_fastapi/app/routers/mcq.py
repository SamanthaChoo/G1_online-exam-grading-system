"""MCQ (Multiple Choice Question) management routes."""

from datetime import datetime, timezone
from typing import Optional

from app.database import get_session
from app.deps import get_current_user, require_role, require_login
from app.models import (
    Exam,
    MCQQuestion,
    MCQAnswer,
    MCQResult,
    User,
    Student,
    Enrollment,
)
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Query
from fastapi import status as http_status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Validation constraints
MCQ_QUESTION_MAX_LENGTH = 5000
MCQ_OPTION_MAX_LENGTH = 1000
VALID_CORRECT_OPTIONS = {"A", "B", "C", "D"}


def _get_exam(exam_id: int, session: Session) -> Exam:
    """Get exam by ID or raise 404."""
    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


def _validate_mcq_inputs(
    question_text: str,
    option_a: str,
    option_b: str,
    option_c: str,
    option_d: str,
    correct_option: str,
) -> dict[str, str]:
    """Validate MCQ inputs and return error dictionary."""
    errors: dict[str, str] = {}

    # Clean inputs
    question_clean = (question_text or "").strip()
    opt_a_clean = (option_a or "").strip()
    opt_b_clean = (option_b or "").strip()
    opt_c_clean = (option_c or "").strip()
    opt_d_clean = (option_d or "").strip()
    correct_clean = (correct_option or "").strip().upper()

    # Validate question text
    if not question_clean:
        errors["question_text"] = "Question text is required."
    elif len(question_clean) > MCQ_QUESTION_MAX_LENGTH:
        errors["question_text"] = (
            f"Question text must be at most {MCQ_QUESTION_MAX_LENGTH} characters."
        )

    # Validate all options are provided and non-empty
    if not opt_a_clean:
        errors["option_a"] = "All options must be provided and non-empty."
    if not opt_b_clean:
        errors["option_b"] = "All options must be provided and non-empty."
    if not opt_c_clean:
        errors["option_c"] = "All options must be provided and non-empty."
    if not opt_d_clean:
        errors["option_d"] = "All options must be provided and non-empty."

    # Validate option lengths (only if not empty, to avoid duplicate error messages)
    if opt_a_clean and len(opt_a_clean) > MCQ_OPTION_MAX_LENGTH:
        errors["option_a"] = (
            f"Option A must be at most {MCQ_OPTION_MAX_LENGTH} characters."
        )
    if opt_b_clean and len(opt_b_clean) > MCQ_OPTION_MAX_LENGTH:
        errors["option_b"] = (
            f"Option B must be at most {MCQ_OPTION_MAX_LENGTH} characters."
        )
    if opt_c_clean and len(opt_c_clean) > MCQ_OPTION_MAX_LENGTH:
        errors["option_c"] = (
            f"Option C must be at most {MCQ_OPTION_MAX_LENGTH} characters."
        )
    if opt_d_clean and len(opt_d_clean) > MCQ_OPTION_MAX_LENGTH:
        errors["option_d"] = (
            f"Option D must be at most {MCQ_OPTION_MAX_LENGTH} characters."
        )

    # Check for duplicate options (case-insensitive)
    if not errors:  # Only check duplicates if basic validation passed
        options = [
            opt_a_clean.lower(),
            opt_b_clean.lower(),
            opt_c_clean.lower(),
            opt_d_clean.lower(),
        ]
        if len(options) != len(set(options)):
            errors["options"] = "All options must be unique."

    # Validate correct_option
    if not correct_clean:
        errors["correct_option"] = "Correct option must be specified."
    elif correct_clean not in VALID_CORRECT_OPTIONS:
        errors["correct_option"] = "Correct option must be one of: A, B, C, or D."

    return errors


@router.get("/mcq/menu")
def mcq_menu(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """Display MCQ management menu."""
    # Get all exams for the current user (if lecturer) or all exams (if admin)
    if current_user.role == "admin":
        exams = session.exec(select(Exam)).all()
    else:
        # For lecturers, filter by their courses
        exams = session.exec(select(Exam)).all()

    context = {
        "request": request,
        "exams": exams,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/mcq_menu.html", context)


@router.get("/{exam_id}/mcq")
def view_mcq_questions(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """View all MCQ questions for an exam."""
    exam = _get_exam(exam_id, session)
    questions = session.exec(
        select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)
    ).all()

    context = {
        "request": request,
        "exam": exam,
        "questions": questions,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/mcq_list.html", context)


@router.get("/{exam_id}/mcq/new")
def new_mcq_form(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """Display form to create a new MCQ question."""
    exam = _get_exam(exam_id, session)
    context = {
        "request": request,
        "exam": exam,
        "errors": {},
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/mcq_form.html", context)


@router.post("/{exam_id}/mcq/new")
async def create_mcq(
    exam_id: int,
    request: Request,
    question_text: Optional[str] = Form(None),
    option_a: Optional[str] = Form(None),
    option_b: Optional[str] = Form(None),
    option_c: Optional[str] = Form(None),
    option_d: Optional[str] = Form(None),
    correct_option: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """Create a new MCQ question for the exam."""
    exam = _get_exam(exam_id, session)

    # Validate inputs
    errors = _validate_mcq_inputs(
        question_text or "",
        option_a or "",
        option_b or "",
        option_c or "",
        option_d or "",
        correct_option or "",
    )

    if errors:
        context = {
            "request": request,
            "exam": exam,
            "errors": errors,
            "form": {
                "question_text": question_text or "",
                "option_a": option_a or "",
                "option_b": option_b or "",
                "option_c": option_c or "",
                "option_d": option_d or "",
                "correct_option": correct_option or "",
            },
            "current_user": current_user,
        }
        return templates.TemplateResponse(
            "exams/mcq_form.html", context, status_code=http_status.HTTP_400_BAD_REQUEST
        )

    # Clean inputs for storage
    question_clean = (question_text or "").strip()
    opt_a_clean = (option_a or "").strip()
    opt_b_clean = (option_b or "").strip()
    opt_c_clean = (option_c or "").strip()
    opt_d_clean = (option_d or "").strip()
    correct_clean = (correct_option or "").strip().upper()

    # Create MCQ question
    mcq = MCQQuestion(
        exam_id=exam.id,
        question_text=question_clean,
        option_a=opt_a_clean,
        option_b=opt_b_clean,
        option_c=opt_c_clean,
        option_d=opt_d_clean,
        correct_option=correct_clean,
    )
    session.add(mcq)
    session.commit()
    session.refresh(mcq)

    # Redirect to MCQ list for this exam
    return RedirectResponse(
        url=f"/exams/{exam_id}/mcq/list",
        status_code=http_status.HTTP_303_SEE_OTHER,
    )


@router.get("/{exam_id}/mcq/list")
def list_mcqs(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """List all MCQ questions for an exam."""
    exam = _get_exam(exam_id, session)
    questions = session.exec(
        select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)
    ).all()

    context = {
        "request": request,
        "exam": exam,
        "questions": questions,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/mcq_list.html", context)


@router.get("/{exam_id}/mcq/{question_id}/edit")
def edit_mcq_form(
    exam_id: int,
    question_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """Display form to edit an MCQ question."""
    exam = _get_exam(exam_id, session)
    question = session.get(MCQQuestion, question_id)
    if not question or question.exam_id != exam_id:
        raise HTTPException(status_code=404, detail="MCQ question not found")

    context = {
        "request": request,
        "exam": exam,
        "question": question,
        "errors": {},
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/mcq_form.html", context)


@router.post("/{exam_id}/mcq/{question_id}/edit")
async def update_mcq(
    exam_id: int,
    question_id: int,
    request: Request,
    question_text: Optional[str] = Form(None),
    option_a: Optional[str] = Form(None),
    option_b: Optional[str] = Form(None),
    option_c: Optional[str] = Form(None),
    option_d: Optional[str] = Form(None),
    correct_option: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """Update an MCQ question."""
    exam = _get_exam(exam_id, session)
    question = session.get(MCQQuestion, question_id)
    if not question or question.exam_id != exam_id:
        raise HTTPException(status_code=404, detail="MCQ question not found")

    # Validate inputs
    errors = _validate_mcq_inputs(
        question_text or "",
        option_a or "",
        option_b or "",
        option_c or "",
        option_d or "",
        correct_option or "",
    )

    if errors:
        context = {
            "request": request,
            "exam": exam,
            "question": question,
            "errors": errors,
            "form": {
                "question_text": question_text or "",
                "option_a": option_a or "",
                "option_b": option_b or "",
                "option_c": option_c or "",
                "option_d": option_d or "",
                "correct_option": correct_option or "",
            },
            "current_user": current_user,
        }
        return templates.TemplateResponse(
            "exams/mcq_form.html", context, status_code=http_status.HTTP_400_BAD_REQUEST
        )

    # Clean inputs for storage
    question_clean = (question_text or "").strip()
    opt_a_clean = (option_a or "").strip()
    opt_b_clean = (option_b or "").strip()
    opt_c_clean = (option_c or "").strip()
    opt_d_clean = (option_d or "").strip()
    correct_clean = (correct_option or "").strip().upper()

    # Update question
    question.question_text = question_clean
    question.option_a = opt_a_clean
    question.option_b = opt_b_clean
    question.option_c = opt_c_clean
    question.option_d = opt_d_clean
    question.correct_option = correct_clean

    session.add(question)
    session.commit()

    return RedirectResponse(
        url=f"/exams/{exam_id}/mcq/list",
        status_code=http_status.HTTP_303_SEE_OTHER,
    )


@router.post("/{exam_id}/mcq/{question_id}/delete")
def delete_mcq(
    exam_id: int,
    question_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """Delete an MCQ question."""
    exam = _get_exam(exam_id, session)
    question = session.get(MCQQuestion, question_id)
    if not question or question.exam_id != exam_id:
        raise HTTPException(status_code=404, detail="MCQ question not found")

    session.delete(question)
    session.commit()

    return RedirectResponse(
        url=f"/exams/{exam_id}/mcq/list",
        status_code=http_status.HTTP_303_SEE_OTHER,
    )


# ============================================================================
# MCQ Student Attempt Routes (Taking the exam with timer + auto-submit)
# ============================================================================


@router.get("/{exam_id}/mcq/start")
def start_mcq_form(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
):
    """Display confirmation page before starting MCQ exam."""
    exam = _get_exam(exam_id, session)

    context = {
        "request": request,
        "exam": exam,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/mcq_start.html", context)


@router.post("/{exam_id}/mcq/start")
def start_mcq_submit(
    exam_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_login),
):
    """Start an MCQ exam attempt - redirect to attempt page."""
    # Only students may start an attempt
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can take exams")

    # Resolve the Student.id linked to this user
    student_id = current_user.student_id
    if student_id is None:
        s = session.exec(
            select(Student).where(Student.user_id == current_user.id)
        ).first()
        if s:
            student_id = s.id

    if student_id is None:
        raise HTTPException(status_code=403, detail="No linked student record found")

    exam = _get_exam(exam_id, session)

    # Check enrollment if exam has a course
    if exam.course_id:
        enrollment = session.exec(
            select(Enrollment).where(
                Enrollment.course_id == exam.course_id,
                Enrollment.student_id == student_id,
            )
        ).first()
        if enrollment is None:
            raise HTTPException(
                status_code=403, detail="You are not enrolled in this course"
            )

    # Check if student already has answers for this exam
    existing_answer = session.exec(
        select(MCQAnswer).where(
            MCQAnswer.exam_id == exam_id,
            MCQAnswer.student_id == student_id,
        )
    ).first()
    if existing_answer:
        raise HTTPException(
            status_code=403, detail="You have already answered this exam"
        )

    # Redirect to attempt page
    return RedirectResponse(
        url=f"/exams/{exam_id}/mcq/attempt",
        status_code=http_status.HTTP_303_SEE_OTHER,
    )


@router.get("/{exam_id}/mcq/attempt")
def mcq_attempt(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_login),
):
    """Display MCQ exam questions with timer and options for student to answer."""
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can take exams")

    exam = _get_exam(exam_id, session)

    # Get all MCQ questions for this exam
    questions = session.exec(
        select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)
    ).all()

    if not questions:
        raise HTTPException(status_code=400, detail="No questions in this exam")

    # Get student record
    student_id = current_user.student_id
    if student_id is None:
        s = session.exec(
            select(Student).where(Student.user_id == current_user.id)
        ).first()
        if s:
            student_id = s.id

    # Get any existing answers (in case student is resuming)
    existing_answers = {}
    if student_id:
        answers = session.exec(
            select(MCQAnswer).where(
                MCQAnswer.exam_id == exam_id,
                MCQAnswer.student_id == student_id,
            )
        ).all()
        existing_answers = {a.question_id: a.selected_option for a in answers}

    # Provide timezone-safe epoch milliseconds for JS countdown
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    context = {
        "request": request,
        "exam": exam,
        "questions": questions,
        "existing_answers": existing_answers,
        "current_user": current_user,
        "student_id": student_id,
        "now_ms": now_ms,
    }
    return templates.TemplateResponse("exams/mcq_attempt.html", context)


@router.post("/{exam_id}/mcq/submit")
async def submit_mcq_attempt(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_login),
):
    """Submit MCQ exam answers and auto-grade."""
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can submit exams")

    # Get student ID
    student_id = current_user.student_id
    if student_id is None:
        s = session.exec(
            select(Student).where(Student.user_id == current_user.id)
        ).first()
        if s:
            student_id = s.id

    if student_id is None:
        raise HTTPException(status_code=403, detail="No linked student record")

    exam = _get_exam(exam_id, session)

    # Read form data
    form = await request.form()

    # Collect answers from fields named answer_{question_id}
    answers_dict = {}
    for key, value in form.items():
        if key.startswith("answer_"):
            try:
                qid = int(key.split("_")[1])
                answers_dict[qid] = value
            except (ValueError, IndexError):
                continue

    # Save each answer to MCQAnswer table
    for qid, selected_option in answers_dict.items():
        # Check if answer already exists
        existing = session.exec(
            select(MCQAnswer).where(
                MCQAnswer.exam_id == exam_id,
                MCQAnswer.question_id == qid,
                MCQAnswer.student_id == student_id,
            )
        ).first()

        if existing:
            existing.selected_option = selected_option
            existing.saved_at = datetime.utcnow()
            session.add(existing)
        else:
            answer = MCQAnswer(
                student_id=student_id,
                exam_id=exam_id,
                question_id=qid,
                selected_option=selected_option,
                saved_at=datetime.utcnow(),
            )
            session.add(answer)

    # Get all questions to auto-grade
    questions = session.exec(
        select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)
    ).all()

    # Calculate score by comparing answers with correct options
    score = 0
    for question in questions:
        selected = answers_dict.get(question.id, "")
        if selected and selected.upper() == question.correct_option:
            score += 1

    # Save or update MCQResult
    existing_result = session.exec(
        select(MCQResult).where(
            MCQResult.exam_id == exam_id,
            MCQResult.student_id == student_id,
        )
    ).first()

    if existing_result:
        existing_result.score = score
        existing_result.total_questions = len(questions)
        existing_result.graded_at = datetime.utcnow()
        session.add(existing_result)
    else:
        result = MCQResult(
            student_id=student_id,
            exam_id=exam_id,
            score=score,
            total_questions=len(questions),
            graded_at=datetime.utcnow(),
        )
        session.add(result)

    session.commit()

    # Redirect to results page
    return RedirectResponse(
        url=f"/exams/{exam_id}/mcq/result",
        status_code=http_status.HTTP_303_SEE_OTHER,
    )


@router.get("/{exam_id}/mcq/result")
def mcq_result(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_login),
):
    """Display MCQ exam result for the student."""
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can view results")

    # Get student ID
    student_id = current_user.student_id
    if student_id is None:
        s = session.exec(
            select(Student).where(Student.user_id == current_user.id)
        ).first()
        if s:
            student_id = s.id

    if student_id is None:
        raise HTTPException(status_code=403, detail="No linked student record")

    exam = _get_exam(exam_id, session)

    # Get result
    result = session.exec(
        select(MCQResult).where(
            MCQResult.exam_id == exam_id,
            MCQResult.student_id == student_id,
        )
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="No result found for this exam")

    # Calculate percentage
    percentage = 0
    if result.total_questions > 0:
        percentage = round((result.score / result.total_questions) * 100, 2)

    context = {
        "request": request,
        "exam": exam,
        "result": result,
        "percentage": percentage,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/mcq_result.html", context)
