"""Exam management routes."""

from datetime import datetime
from typing import Optional

from app.database import get_session
from app.deps import get_current_user, require_role
from app.models import (
    Course,
    Exam,
    ExamQuestion,
    User,
    Student,
    Enrollment,
    MCQResult,
    MCQQuestion,
    MCQAnswer,
    CourseLecturer,
    ExamActivityLog,
)
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi import status as http_status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

STATUS_OPTIONS = ["draft", "scheduled", "completed"]
EXAM_TITLE_MAX_LENGTH = 200
EXAM_SUBJECT_MAX_LENGTH = 120
EXAM_DURATION_MAX_MINUTES = 600
EXAM_INSTRUCTIONS_MAX_LENGTH = 2000  # 2,000 characters max for instructions (roughly 1-2 pages)
ITEMS_PER_PAGE = 10  # Number of items per page for pagination


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _get_exam(exam_id: int, session: Session) -> Exam:
    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


# ===================== SPRINT 1: STUDENT ROUTES =====================


def _has_mcq_result(session: Session, exam_id: int, student_id: int) -> bool:
    """Return True if the student has a graded MCQ result for this exam (i.e. one attempt already used)."""
    existing = session.exec(
        select(MCQResult).where(MCQResult.exam_id == exam_id, MCQResult.student_id == student_id)
    ).first()
    return existing is not None


@router.get("/results/student/{student_id}")
def student_exam_results(
    student_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    """View exam results for a specific student."""
    student = session.get(Student, student_id)

    # Get all MCQ results for this student
    mcq_results = session.exec(
        select(MCQResult, Exam, Course)
        .join(Exam, MCQResult.exam_id == Exam.id)
        .join(Course, Exam.course_id == Course.id)
        .where(MCQResult.student_id == student_id)
        .order_by(MCQResult.graded_at.desc())
    ).all()

    # Format results with additional info
    results_list = []
    total_exams = len(mcq_results)
    total_score = 0
    total_questions = 0

    for result, exam, course in mcq_results:
        percentage = (result.score / result.total_questions * 100) if result.total_questions > 0 else 0
        total_score += result.score
        total_questions += result.total_questions

        results_list.append({"result": result, "exam": exam, "course": course, "percentage": percentage})

    # Calculate overall statistics
    overall_percentage = (total_score / total_questions * 100) if total_questions > 0 else 0

    context = {
        "request": request,
        "student": student,
        "results": results_list,
        "total_exams": total_exams,
        "total_score": total_score,
        "total_questions": total_questions,
        "overall_percentage": overall_percentage,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/results.html", context)


@router.get("/{exam_id}/start")
def start_exam_page(
    exam_id: int,
    request: Request,
    student_id: int = Query(...),
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    exam = session.get(Exam, exam_id)
    student = session.get(Student, student_id)

    # If the student has already completed this MCQ exam, send them to the finished page.
    if student and exam and _has_mcq_result(session, exam_id, student_id):
        return RedirectResponse(
            url="/exams/exam_finished",
            status_code=http_status.HTTP_303_SEE_OTHER,
        )

    now = datetime.now()
    can_start = False
    countdown = None
    if exam and exam.start_time:
        mins_to_start = (exam.start_time - now).total_seconds() / 60
        # If exam is within 30 minutes, allow start flow with countdown
        if 0 <= mins_to_start <= 30:
            can_start = True
            countdown = int((exam.start_time - now).total_seconds())
        # If exam is already ongoing, allow immediate join (countdown 0)
        elif exam.start_time <= now and exam.end_time and now <= exam.end_time:
            can_start = True
            countdown = 0
    context = {
        "request": request,
        "exam": exam,
        "student": student,
        "can_start": can_start,
        "countdown": countdown,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/start_exam.html", context)


@router.get("/{exam_id}/join")
def join_exam(
    exam_id: int,
    request: Request,
    student_id: int = Query(...),
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    from datetime import datetime
    from app.models import ExamAttempt

    exam = session.get(Exam, exam_id)
    student = session.get(Student, student_id)

    # Enforce single attempt: if MCQ result already exists, redirect to finished page.
    if student and exam and _has_mcq_result(session, exam_id, student_id):
        return RedirectResponse(
            url="/exams/exam_finished",
            status_code=http_status.HTTP_303_SEE_OTHER,
        )

    # Check if student has already submitted essay attempt (status = submitted or is_final = 1)
    essay_attempt = session.exec(
        select(ExamAttempt).where(
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.student_id == student_id,
            ExamAttempt.is_final == 1,
        )
    ).first()
    if essay_attempt:
        return RedirectResponse(
            url="/exams/exam_finished",
            status_code=http_status.HTTP_303_SEE_OTHER,
        )

    # Get MCQ questions
    mcq_questions = session.exec(select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)).all()
    # Get essay questions
    essay_questions = session.exec(select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)).all()

    # Get any existing MCQ answers
    mcq_answers = session.exec(
        select(MCQAnswer).where(
            MCQAnswer.exam_id == exam_id,
            MCQAnswer.student_id == student_id,
        )
    ).all()
    mcq_answer_map = {a.question_id: a.selected_option for a in mcq_answers}

    # Determine if we should auto-grade: only if there are ONLY MCQ questions (no essay)
    has_only_mcq = len(mcq_questions) > 0 and len(essay_questions) == 0

    # Calculate time left in milliseconds based on exam end_time
    time_left_ms = None
    if exam and exam.end_time:
        now = datetime.utcnow()
        time_diff = exam.end_time - now
        time_left_ms = int(time_diff.total_seconds() * 1000)
        # If time is already up, redirect to finished
        if time_left_ms <= 0:
            return RedirectResponse(
                url="/exams/exam_finished",
                status_code=http_status.HTTP_303_SEE_OTHER,
            )

    context = {
        "request": request,
        "exam": exam,
        "student": student,
        "mcq_questions": mcq_questions,
        "essay_questions": essay_questions,
        "answer_map": mcq_answer_map,
        "has_only_mcq": has_only_mcq,
        "current_user": current_user,
        "exam_end_time": exam.end_time.isoformat() if exam and exam.end_time else None,
    }
    return templates.TemplateResponse("exams/join_exam.html", context)


@router.post("/{exam_id}/submit-essay")
async def submit_essay_attempt(exam_id: int, request: Request, session: Session = Depends(get_session)):
    """Mark an essay attempt as submitted/final."""
    from app.models import ExamAttempt

    data = await request.json()
    student_id = data.get("student_id")

    # Get the essay attempt
    attempt = session.exec(
        select(ExamAttempt).where(
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.student_id == student_id,
        )
    ).first()

    if attempt:
        attempt.status = "submitted"
        attempt.is_final = 1
        attempt.submitted_at = datetime.utcnow()
        session.add(attempt)
        session.commit()

    return {"status": "success"}


@router.post("/{exam_id}/log-activity")
async def log_exam_activity(exam_id: int, request: Request, session: Session = Depends(get_session)):
    """Log suspicious activities during exam taking for anti-cheating purposes."""
    data = await request.json()
    student_id = data.get("student_id")
    attempt_id = data.get("attempt_id")  # Optional, for essay attempts
    activity_type = data.get("activity_type")
    metadata = data.get("metadata")  # Optional JSON string or dict
    severity = data.get("severity", "low")  # low, medium, high

    if not student_id or not activity_type:
        return {
            "status": "error",
            "message": "student_id and activity_type are required",
        }

    # Validate exam exists
    exam = session.get(Exam, exam_id)
    if not exam:
        return {"status": "error", "message": "Exam not found"}

    # Validate student exists
    student = session.get(Student, student_id)
    if not student:
        return {"status": "error", "message": "Student not found"}

    # Convert metadata to JSON string if it's a dict
    metadata_str = None
    if metadata:
        if isinstance(metadata, dict):
            import json

            metadata_str = json.dumps(metadata)
        else:
            metadata_str = str(metadata)

    # Create activity log entry
    activity_log = ExamActivityLog(
        exam_id=exam_id,
        student_id=student_id,
        attempt_id=attempt_id,
        activity_type=activity_type,
        activity_metadata=metadata_str,
        severity=severity,
        timestamp=datetime.utcnow(),
    )
    session.add(activity_log)
    session.commit()

    return {"status": "success", "log_id": activity_log.id}


@router.post("/{exam_id}/autosave")
async def autosave_answers(exam_id: int, request: Request, session: Session = Depends(get_session)):
    from app.models import ExamAttempt, EssayAnswer

    data = await request.json()
    student_id = data.get("student_id")
    mcq_answers = data.get("answers", {})
    essay_answers = data.get("essay_answers", {})

    # Save MCQ answers
    for qid, selected in mcq_answers.items():
        qid = int(qid)
        answer = session.exec(
            select(MCQAnswer).where(
                MCQAnswer.exam_id == exam_id,
                MCQAnswer.student_id == student_id,
                MCQAnswer.question_id == qid,
            )
        ).first()
        if answer:
            answer.selected_option = selected
            answer.saved_at = datetime.utcnow()
            session.add(answer)
        else:
            session.add(
                MCQAnswer(
                    student_id=student_id,
                    exam_id=exam_id,
                    question_id=qid,
                    selected_option=selected,
                )
            )

    # Save essay answers
    if essay_answers:
        # Get or create essay attempt for this student
        attempt = session.exec(
            select(ExamAttempt).where(
                ExamAttempt.exam_id == exam_id,
                ExamAttempt.student_id == student_id,
            )
        ).first()

        if not attempt:
            attempt = ExamAttempt(
                exam_id=exam_id,
                student_id=student_id,
                started_at=datetime.utcnow(),
                status="in_progress",
                is_final=0,
            )
            session.add(attempt)
            session.flush()

        # Save each essay answer
        for qid_str, answer_text in essay_answers.items():
            qid = int(qid_str)
            essay_answer = session.exec(
                select(EssayAnswer).where(
                    EssayAnswer.attempt_id == attempt.id,
                    EssayAnswer.question_id == qid,
                )
            ).first()

            if essay_answer:
                essay_answer.answer_text = answer_text
                session.add(essay_answer)
            else:
                session.add(
                    EssayAnswer(
                        attempt_id=attempt.id,
                        question_id=qid,
                        answer_text=answer_text,
                    )
                )

    session.commit()
    return {"status": "success"}


@router.post("/{exam_id}/submit")
async def submit_exam(exam_id: int, request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    student_id = data.get("student_id")
    answers = data.get("answers", {})

    # Prevent multiple submissions: if a graded result already exists, return it unchanged.
    existing_result = session.exec(
        select(MCQResult).where(MCQResult.exam_id == exam_id, MCQResult.student_id == student_id)
    ).first()
    if existing_result is not None:
        return {
            "status": "already_submitted",
            "score": existing_result.score,
            "total": existing_result.total_questions,
        }
    # Save answers
    for qid, selected in answers.items():
        qid = int(qid)
        answer = session.exec(
            select(MCQAnswer).where(
                MCQAnswer.exam_id == exam_id,
                MCQAnswer.student_id == student_id,
                MCQAnswer.question_id == qid,
            )
        ).first()
        if answer:
            answer.selected_option = selected
            answer.saved_at = datetime.utcnow()
            session.add(answer)
        else:
            session.add(
                MCQAnswer(
                    student_id=student_id,
                    exam_id=exam_id,
                    question_id=qid,
                    selected_option=selected,
                )
            )
    session.commit()
    # Auto-grade
    questions = session.exec(select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)).all()
    correct = 0
    for q in questions:
        ans = session.exec(
            select(MCQAnswer).where(
                MCQAnswer.exam_id == exam_id,
                MCQAnswer.student_id == student_id,
                MCQAnswer.question_id == q.id,
            )
        ).first()
        if ans and ans.selected_option == q.correct_option:
            correct += 1
    total = len(questions)
    result = MCQResult(
        student_id=student_id,
        exam_id=exam_id,
        score=correct,
        total_questions=total,
        graded_at=datetime.utcnow(),
    )
    session.add(result)
    session.commit()
    return {"status": "graded", "score": correct, "total": total}


# ===================== SPRINT 1: LECTURER MCQ MANAGEMENT =====================


@router.get("/{exam_id}/mcq")
def list_mcqs(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    exam = session.get(Exam, exam_id)
    questions = session.exec(select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)).all()
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
    exam = session.get(Exam, exam_id)
    context = {
        "request": request,
        "exam": exam,
        "form": None,
        "errors": {},
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/mcq_form.html", context)


@router.post("/{exam_id}/mcq/new")
def create_mcq(
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
    """Create a new MCQ with basic validation and friendly 400 errors instead of 422."""

    errors: dict[str, str] = {}

    # Normalise inputs
    q_text = (question_text or "").strip()
    a = (option_a or "").strip()
    b = (option_b or "").strip()
    c = (option_c or "").strip()
    d = (option_d or "").strip()
    correct = (correct_option or "").strip()

    # Question text validation
    if not q_text:
        errors["question_text"] = "Question text must be provided and non-empty."
    elif len(q_text) < 5:
        errors["question_text"] = "Question text must be at least 5 characters long."

    # Options must all be present and non-empty
    options = {"A": a, "B": b, "C": c, "D": d}
    if any(not val for val in options.values()):
        errors["options"] = "All options (A, B, C, D) must be provided and non-empty."
    else:
        # Check for duplicate options (case-insensitive)
        normalized = [val.lower() for val in options.values()]
        if len(set(normalized)) != len(normalized):
            errors["options"] = "Options A, B, C and D must all be different (unique)."

    # Correct option validation: must be one of A/B/C/D (case-insensitive)
    if not correct:
        errors["correct_option"] = "Correct option must be provided."
    else:
        correct_upper = correct.upper()
        if correct_upper not in {"A", "B", "C", "D"}:
            errors["correct_option"] = "Correct option must be one of A, B, C or D."

    if errors:
        exam = session.get(Exam, exam_id)
        form = {
            "question_text": question_text or "",
            "option_a": option_a or "",
            "option_b": option_b or "",
            "option_c": option_c or "",
            "option_d": option_d or "",
            "correct_option": correct_option or "",
        }
        context = {
            "request": request,
            "exam": exam,
            "form": form,
            "errors": errors,
            "current_user": current_user,
        }
        return templates.TemplateResponse("exams/mcq_form.html", context, status_code=http_status.HTTP_400_BAD_REQUEST)

    mcq = MCQQuestion(
        exam_id=exam_id,
        question_text=q_text,
        option_a=a,
        option_b=b,
        option_c=c,
        option_d=d,
        correct_option=correct.upper(),
    )
    session.add(mcq)
    session.commit()
    return RedirectResponse(
        url=f"/exams/{exam_id}/mcq",
        status_code=http_status.HTTP_303_SEE_OTHER,
    )


@router.get("/mcq/{question_id}/edit")
def edit_mcq_form(
    question_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    mcq = session.get(MCQQuestion, question_id)
    exam = session.get(Exam, mcq.exam_id) if mcq else None
    context = {
        "request": request,
        "mcq": mcq,
        "exam": exam,
        "form": None,
        "errors": {},
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/mcq_form.html", context)


@router.post("/mcq/{question_id}/edit")
def update_mcq(
    question_id: int,
    request: Request,
    question_text: str = Form(...),
    option_a: str = Form(...),
    option_b: str = Form(...),
    option_c: str = Form(...),
    option_d: str = Form(...),
    correct_option: str = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    mcq = session.get(MCQQuestion, question_id)
    if not mcq:
        raise HTTPException(status_code=404, detail="MCQ not found")
    mcq.question_text = question_text.strip()
    mcq.option_a = option_a.strip()
    mcq.option_b = option_b.strip()
    mcq.option_c = option_c.strip()
    mcq.option_d = option_d.strip()
    mcq.correct_option = correct_option.strip()
    session.add(mcq)
    session.commit()
    return RedirectResponse(url=f"/exams/{mcq.exam_id}/mcq", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/mcq/{question_id}/delete")
def delete_mcq(
    question_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    mcq = session.get(MCQQuestion, question_id)
    exam_id = mcq.exam_id if mcq else None
    if mcq:
        session.delete(mcq)
        session.commit()
    return RedirectResponse(url=f"/exams/{exam_id}/mcq", status_code=http_status.HTTP_303_SEE_OTHER)


@router.get("/new")
def new_exam_form(
    request: Request,
    course_id: Optional[int] = Query(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    courses = session.exec(select(Course).order_by(Course.name)).all()
    context = {
        "request": request,
        "courses": courses,
        "exam": None,
        "form": None,
        "errors": {},
        # Do not preselect a course; let the user choose explicitly
        "selected_course_id": None,
        "mode": "create",
        "status_options": STATUS_OPTIONS,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/form.html", context)


@router.post("/new")
async def create_exam(
    request: Request,
    title: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    duration_minutes: Optional[str] = Form(None),
    course_id: Optional[str] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    instructions: Optional[str] = Form(None),
    status: Optional[str] = Form("draft"),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    errors: dict[str, str] = {}

    title_clean = (title or "").strip()
    subject_clean = (subject or "").strip()
    instructions_clean = (instructions or "").strip()

    # Required text fields
    if not title_clean:
        errors["title"] = "Exam title is required."
    elif len(title_clean) > EXAM_TITLE_MAX_LENGTH:
        errors["title"] = f"Title must be at most {EXAM_TITLE_MAX_LENGTH} characters."
    elif len(title_clean) > EXAM_TITLE_MAX_LENGTH:
        errors["title"] = f"Title must be at most {EXAM_TITLE_MAX_LENGTH} characters."
    if not subject_clean:
        errors["subject"] = "Exam subject is required."
    elif len(subject_clean) > EXAM_SUBJECT_MAX_LENGTH:
        errors["subject"] = f"Subject must be at most {EXAM_SUBJECT_MAX_LENGTH} characters."

    # Instructions validation (optional field, but has max length if provided)
    if instructions_clean and len(instructions_clean) > EXAM_INSTRUCTIONS_MAX_LENGTH:
        errors["instructions"] = f"Instructions must be at most {EXAM_INSTRUCTIONS_MAX_LENGTH} characters."

    # Duration validation
    if not duration_minutes or not duration_minutes.strip():
        errors["duration_minutes"] = "Duration is required."
        duration_value = 0
    else:
        try:
            duration_value = int(duration_minutes.strip())
            if duration_value <= 0:
                errors["duration_minutes"] = "Duration must be greater than zero."
            elif duration_value > EXAM_DURATION_MAX_MINUTES:
                errors["duration_minutes"] = f"Duration cannot exceed {EXAM_DURATION_MAX_MINUTES} minutes."
        except (TypeError, ValueError):
            errors["duration_minutes"] = "Duration must be a valid number of minutes."
            duration_value = 0

    # Course validation
    course_id_int: Optional[int] = None
    if not course_id:
        errors["course_id"] = "Please select a course for this exam."
    else:
        try:
            course_id_int = int(course_id)
        except (TypeError, ValueError):
            errors["course_id"] = "Please select a valid course."
        else:
            course = session.get(Course, course_id_int)
            if not course:
                errors["course_id"] = "Selected course does not exist."

    # Datetime validation
    if not start_time:
        errors["start_time"] = "Exam start time is required."
        start_dt = None
    else:
        try:
            start_dt = _parse_datetime(start_time)
            # Check if start time is before today (current date/time)
            if start_dt:
                from datetime import timezone, timedelta

                # Get current time as UTC (timezone-aware) for comparison
                now_aware = datetime.now(timezone.utc)
                # Normalize start_dt to UTC (timezone-aware) for comparison
                if start_dt.tzinfo is None:
                    # If timezone-naive, assume it's UTC and make it aware for comparison
                    start_dt_aware = start_dt.replace(tzinfo=timezone.utc)
                else:
                    # If timezone-aware, convert to UTC
                    start_dt_aware = start_dt.astimezone(timezone.utc)
                # Allow a small buffer (5 seconds) to account for processing time between
                # generating the time string and validating it
                buffer = timedelta(seconds=5)
                # Compare timezone-aware datetimes (both in UTC)
                if start_dt_aware < (now_aware - buffer):
                    errors["start_time"] = "Exam start time cannot be in the past."
                    start_dt = None
                else:
                    # Convert back to naive UTC for database storage (database expects naive)
                    start_dt = start_dt_aware.replace(tzinfo=None)
        except ValueError:
            start_dt = None
            errors["start_time"] = "Start time format is invalid."

    if not end_time:
        errors["end_time"] = "Exam end time is required."
        end_dt = None
    else:
        try:
            end_dt = _parse_datetime(end_time)
            # Normalize end_dt to naive UTC for database storage (consistent with start_dt)
            if end_dt:
                from datetime import timezone

                if end_dt.tzinfo is None:
                    # Already naive, assume UTC
                    pass
                else:
                    # Convert timezone-aware to naive UTC
                    end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            end_dt = None
            errors["end_time"] = "End time format is invalid."

    if start_dt and end_dt and end_dt <= start_dt:
        errors["end_time"] = "End time must be after the start time."

    # Status validation
    status_clean = (status or "").strip().lower()
    if status_clean not in STATUS_OPTIONS:
        errors["status"] = "Please select a valid status."

    if errors:
        courses = session.exec(select(Course).order_by(Course.name)).all()
        form = {
            "title": title or "",
            "subject": subject or "",
            "duration_minutes": duration_minutes or "",
            "course_id": course_id or "",
            "start_time": start_time or "",
            "end_time": end_time or "",
            "instructions": instructions_clean,
            "status": status_clean or "draft",
        }
        context = {
            "request": request,
            "courses": courses,
            "exam": None,
            "form": form,
            "errors": errors,
            "selected_course_id": int(course_id) if course_id else None,
            "mode": "create",
            "status_options": STATUS_OPTIONS,
            "current_user": current_user,
        }
        return templates.TemplateResponse("exams/form.html", context, status_code=http_status.HTTP_400_BAD_REQUEST)

    exam = Exam(
        title=title_clean,
        subject=subject_clean,
        duration_minutes=duration_value,
        course_id=course_id_int if course_id_int is not None else None,
        start_time=start_dt,
        end_time=end_dt,
        instructions=instructions_clean or None,
        status=status_clean,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(exam)
    session.commit()
    session.refresh(exam)
    return RedirectResponse(url=f"/exams/{exam.id}", status_code=http_status.HTTP_303_SEE_OTHER)


@router.get("/course/{course_id}")
def exams_for_course(
    course_id: int,
    request: Request,
    sort: Optional[str] = Query("start"),
    direction: Optional[str] = Query("asc"),
    page: Optional[int] = Query(1, ge=1),
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List all exams associated with a specific course, with optional sorting and pagination."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    exams = session.exec(select(Exam).where(Exam.course_id == course_id)).all()

    key_map = {
        "title": lambda e: e.title or "",
        "subject": lambda e: e.subject or "",
        "start": lambda e: e.start_time or datetime.max,
        "end": lambda e: e.end_time or datetime.max,
        "duration": lambda e: e.duration_minutes or 0,
        "status": lambda e: (e.status or "").lower(),
    }

    sort_key = key_map.get(sort or "start", key_map["start"])
    is_desc = (direction or "asc").lower() == "desc"
    exams_sorted = sorted(exams, key=sort_key, reverse=is_desc)

    # Pagination
    total_exams = len(exams_sorted)
    total_pages = (total_exams + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_exams > 0 else 1
    page = min(page, total_pages) if total_pages > 0 else 1
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    exams_paginated = exams_sorted[start_idx:end_idx]

    has_sort = (sort not in (None, "", "start")) or ((direction or "asc").lower() != "asc")

    context = {
        "request": request,
        "course": course,
        "exams": exams_paginated,
        "sort": sort,
        "direction": "desc" if is_desc else "asc",
        "has_sort": has_sort,
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total_exams,
        "items_per_page": ITEMS_PER_PAGE,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/list_by_course.html", context)


@router.get("/exam_finished")
def exam_finished(
    request: Request,
    score: Optional[int] = Query(None),
    total: Optional[int] = Query(None),
    current_user: Optional[User] = Depends(get_current_user),
):
    context = {
        "request": request,
        "current_user": current_user,
        "score": score,
        "total": total,
    }
    return templates.TemplateResponse("exams/exam_finished.html", context)


@router.get("/results/lecturer")
def lecturer_results_overview(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """View all exam results overview for lecturer."""
    # Get all courses taught by the lecturer (or all courses for admin)
    if current_user.role == "admin":
        courses = session.exec(select(Course)).all()
    else:
        # Get courses where user is a lecturer
        course_lecturer_links = session.exec(
            select(CourseLecturer).where(CourseLecturer.lecturer_id == current_user.id)
        ).all()
        course_ids = [link.course_id for link in course_lecturer_links]
        courses = session.exec(select(Course).where(Course.id.in_(course_ids))).all() if course_ids else []

    # Get exam statistics for each course
    course_stats = []
    for course in courses:
        exams = session.exec(select(Exam).where(Exam.course_id == course.id)).all()
        total_exams = len(exams)
        total_students = session.exec(select(Enrollment).where(Enrollment.course_id == course.id)).all()

        # Count completed exams (exams with results)
        completed_count = 0
        for exam in exams:
            results_count = session.exec(select(MCQResult).where(MCQResult.exam_id == exam.id)).all()
            if len(results_count) > 0:
                completed_count += 1

        course_stats.append(
            {
                "course": course,
                "total_exams": total_exams,
                "completed_exams": completed_count,
                "total_students": len(total_students),
            }
        )

    context = {
        "request": request,
        "current_user": current_user,
        "course_stats": course_stats,
    }
    return templates.TemplateResponse("exams/lecturer_results.html", context)


@router.get("/results/course/{course_id}")
def course_results(
    course_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """View all exam results for a specific course."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Get all exams for this course
    exams = session.exec(select(Exam).where(Exam.course_id == course_id)).all()

    # Get result statistics for each exam
    exam_results = []
    for exam in exams:
        results = session.exec(select(MCQResult).where(MCQResult.exam_id == exam.id)).all()

        if results:
            total_students = len(results)
            total_score = sum(r.score for r in results)
            total_questions = sum(r.total_questions for r in results)
            avg_percentage = (total_score / total_questions * 100) if total_questions > 0 else 0
            highest_score = max(r.score for r in results)
            lowest_score = min(r.score for r in results)

            exam_results.append(
                {
                    "exam": exam,
                    "total_students": total_students,
                    "avg_percentage": avg_percentage,
                    "highest_score": highest_score,
                    "lowest_score": lowest_score,
                    "total_questions": results[0].total_questions if results else 0,
                }
            )
        else:
            exam_results.append(
                {
                    "exam": exam,
                    "total_students": 0,
                    "avg_percentage": 0,
                    "highest_score": 0,
                    "lowest_score": 0,
                    "total_questions": 0,
                }
            )

    context = {
        "request": request,
        "current_user": current_user,
        "course": course,
        "exam_results": exam_results,
    }
    return templates.TemplateResponse("exams/course_results.html", context)


@router.get("/results/exam/{exam_id}")
def exam_results_detail(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """View detailed results for a specific exam (all students)."""
    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    course = session.get(Course, exam.course_id)

    # Get all results for this exam with student info
    results = session.exec(
        select(MCQResult, Student)
        .join(Student, MCQResult.student_id == Student.id)
        .where(MCQResult.exam_id == exam_id)
        .order_by(MCQResult.score.desc())
    ).all()

    # Format results
    student_results = []
    for result, student in results:
        percentage = (result.score / result.total_questions * 100) if result.total_questions > 0 else 0
        student_results.append({"student": student, "result": result, "percentage": percentage})

    # Calculate statistics
    if results:
        scores = [r.score for r, _ in results]
        total_questions = results[0][0].total_questions if results else 0
        avg_score = sum(scores) / len(scores)
        avg_percentage = (avg_score / total_questions * 100) if total_questions > 0 else 0
        highest_score = max(scores)
        lowest_score = min(scores)
        pass_count = sum(1 for r, _ in results if (r.score / r.total_questions * 100) >= 50)
        pass_rate = (pass_count / len(results) * 100) if results else 0
    else:
        avg_percentage = 0
        highest_score = 0
        lowest_score = 0
        pass_rate = 0
        total_questions = 0

    context = {
        "request": request,
        "current_user": current_user,
        "exam": exam,
        "course": course,
        "student_results": student_results,
        "total_students": len(results),
        "avg_percentage": avg_percentage,
        "highest_score": highest_score,
        "lowest_score": lowest_score,
        "pass_rate": pass_rate,
        "total_questions": total_questions,
    }
    return templates.TemplateResponse("exams/exam_results_detail.html", context)


@router.get("/{exam_id}")
def exam_detail(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    exam = _get_exam(exam_id, session)
    course = session.get(Course, exam.course_id) if exam.course_id else None
    context = {
        "request": request,
        "exam": exam,
        "course": course,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/detail.html", context)


@router.get("/{exam_id}/edit")
def edit_exam_form(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    exam = _get_exam(exam_id, session)
    courses = session.exec(select(Course).order_by(Course.name)).all()
    context = {
        "request": request,
        "exam": exam,
        "form": None,
        "errors": {},
        "courses": courses,
        "selected_course_id": exam.course_id,
        "mode": "edit",
        "status_options": STATUS_OPTIONS,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/form.html", context)


@router.post("/{exam_id}/edit")
async def update_exam(
    exam_id: int,
    request: Request,
    title: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    duration_minutes: Optional[str] = Form(None),
    course_id: Optional[str] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    instructions: Optional[str] = Form(None),
    status: Optional[str] = Form("draft"),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    exam = _get_exam(exam_id, session)

    errors: dict[str, str] = {}

    title_clean = (title or "").strip()
    subject_clean = (subject or "").strip()
    instructions_clean = (instructions or "").strip()

    if not title_clean:
        errors["title"] = "Exam title is required."
    elif len(title_clean) > EXAM_TITLE_MAX_LENGTH:
        errors["title"] = f"Title must be at most {EXAM_TITLE_MAX_LENGTH} characters."
    if not subject_clean:
        errors["subject"] = "Exam subject is required."
    elif len(subject_clean) > EXAM_SUBJECT_MAX_LENGTH:
        errors["subject"] = f"Subject must be at most {EXAM_SUBJECT_MAX_LENGTH} characters."

    # Instructions validation (optional field, but has max length if provided)
    if instructions_clean and len(instructions_clean) > EXAM_INSTRUCTIONS_MAX_LENGTH:
        errors["instructions"] = f"Instructions must be at most {EXAM_INSTRUCTIONS_MAX_LENGTH} characters."

    if not duration_minutes or not duration_minutes.strip():
        errors["duration_minutes"] = "Duration is required."
        duration_value = 0
    else:
        try:
            duration_value = int(duration_minutes.strip())
            if duration_value <= 0:
                errors["duration_minutes"] = "Duration must be greater than zero."
            elif duration_value > EXAM_DURATION_MAX_MINUTES:
                errors["duration_minutes"] = f"Duration cannot exceed {EXAM_DURATION_MAX_MINUTES} minutes."
        except (TypeError, ValueError):
            errors["duration_minutes"] = "Duration must be a valid number of minutes."
            duration_value = 0

    course_id_int: Optional[int] = None
    if not course_id:
        errors["course_id"] = "Please select a course for this exam."
    else:
        try:
            course_id_int = int(course_id)
        except (TypeError, ValueError):
            errors["course_id"] = "Please select a valid course."
        else:
            course = session.get(Course, course_id_int)
            if not course:
                errors["course_id"] = "Selected course does not exist."

    if not start_time:
        errors["start_time"] = "Exam start time is required."
        start_dt = None
    else:
        try:
            start_dt = _parse_datetime(start_time)
            # Check if start time is before today (current date/time)
            if start_dt:
                from datetime import timezone, timedelta

                # Get current time as UTC (timezone-aware) for comparison
                now_aware = datetime.now(timezone.utc)
                # Normalize start_dt to UTC (timezone-aware) for comparison
                if start_dt.tzinfo is None:
                    # If timezone-naive, assume it's UTC and make it aware for comparison
                    start_dt_aware = start_dt.replace(tzinfo=timezone.utc)
                else:
                    # If timezone-aware, convert to UTC
                    start_dt_aware = start_dt.astimezone(timezone.utc)
                # Allow a small buffer (5 seconds) to account for processing time between
                # generating the time string and validating it
                buffer = timedelta(seconds=5)
                # Compare timezone-aware datetimes (both in UTC)
                if start_dt_aware < (now_aware - buffer):
                    errors["start_time"] = "Exam start time cannot be in the past."
                    start_dt = None
                else:
                    # Convert back to naive UTC for database storage (database expects naive)
                    start_dt = start_dt_aware.replace(tzinfo=None)
        except ValueError:
            start_dt = None
            errors["start_time"] = "Start time format is invalid."

    if not end_time:
        errors["end_time"] = "Exam end time is required."
        end_dt = None
    else:
        try:
            end_dt = _parse_datetime(end_time)
            # Normalize end_dt to naive UTC for database storage (consistent with start_dt)
            if end_dt:
                from datetime import timezone

                if end_dt.tzinfo is None:
                    # Already naive, assume UTC
                    pass
                else:
                    # Convert timezone-aware to naive UTC
                    end_dt = end_dt.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            end_dt = None
            errors["end_time"] = "End time format is invalid."

    if start_dt and end_dt and end_dt <= start_dt:
        errors["end_time"] = "End time must be after the start time."

    status_clean = (status or "").strip().lower()
    if status_clean not in STATUS_OPTIONS:
        errors["status"] = "Please select a valid status."

    if errors:
        courses = session.exec(select(Course).order_by(Course.name)).all()
        form = {
            "title": title or "",
            "subject": subject or "",
            "duration_minutes": duration_minutes or "",
            "course_id": course_id or "",
            "start_time": start_time or "",
            "end_time": end_time or "",
            "instructions": instructions_clean,
            "status": status_clean or exam.status,
        }
        context = {
            "request": request,
            "exam": exam,
            "form": form,
            "errors": errors,
            "courses": courses,
            "selected_course_id": int(course_id) if course_id else None,
            "mode": "edit",
            "status_options": STATUS_OPTIONS,
            "current_user": current_user,
        }
        return templates.TemplateResponse("exams/form.html", context, status_code=http_status.HTTP_400_BAD_REQUEST)

    exam.title = title_clean
    exam.subject = subject_clean
    exam.duration_minutes = duration_value
    exam.course_id = course_id_int if course_id_int is not None else None
    exam.start_time = start_dt
    exam.end_time = end_dt
    exam.instructions = instructions_clean or None
    exam.status = status_clean
    exam.updated_at = datetime.utcnow()

    session.add(exam)
    session.commit()

    return RedirectResponse(url=f"/exams/{exam.id}", status_code=http_status.HTTP_303_SEE_OTHER)


@router.get("/{exam_id}/start")
def start_exam(
    request: Request,
    exam_id: int,
    student_id: int = Query(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Start an exam attempt - redirect to MCQ or essay based on exam type."""
    from app.models import Student

    try:
        # Verify exam exists
        exam = session.get(Exam, exam_id)
        if not exam:
            raise HTTPException(status_code=404, detail="Exam not found")

        # Verify student exists
        student = session.get(Student, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Check if exam has MCQ questions
        from app.models import MCQQuestion

        mcq_count = session.exec(select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)).first()

        # Redirect to appropriate exam type
        if mcq_count:
            # Has MCQ questions
            return RedirectResponse(
                url=f"/exams/{exam_id}/mcq/start?student_id={student_id}",
                status_code=303,
            )
        else:
            # Essay exam
            return RedirectResponse(url=f"/essay/{exam_id}/start?student_id={student_id}", status_code=303)

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error starting exam: {str(e)}")


@router.get("/schedule/student/{student_id}")
def view_exam_schedule(
    request: Request,
    student_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Display exam schedule for a student showing all exams in their enrolled courses."""
    from app.models import Student, Enrollment

    try:
        # Verify student exists
        student = session.get(Student, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Get student's enrolled courses
        enrollments = session.exec(select(Enrollment).where(Enrollment.student_id == student_id)).all()

        course_ids = [enrollment.course_id for enrollment in enrollments]

        # Get all exams from enrolled courses, sorted by start_time
        exams = []
        if course_ids:
            exams = session.exec(
                select(Exam)
                .where(Exam.course_id.in_(course_ids))
                .where(Exam.status.in_(["scheduled", "completed"]))
                .order_by(Exam.start_time)
            ).all()

        context = {
            "request": request,
            "student": student,
            "exams": exams,
            "current_user": current_user,
        }
        return templates.TemplateResponse("exams/schedule.html", context)

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading schedule: {str(e)}")


@router.get("/schedule/student/{student_id}")
def student_exam_schedule(
    request: Request,
    student_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Display exam schedule for a specific student."""
    from app.models import Student, Enrollment

    try:
        # Get student record
        student = session.get(Student, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Get enrolled courses
        enrollments = session.exec(select(Enrollment).where(Enrollment.student_id == student_id)).all()

        course_ids = [e.course_id for e in enrollments]

        # Get exams for enrolled courses
        if course_ids:
            exams = session.exec(
                select(Exam)
                .where(Exam.course_id.in_(course_ids))
                .where(Exam.status == "scheduled")
                .order_by(Exam.start_time)
            ).all()
        else:
            exams = []

        context = {
            "request": request,
            "student": student,
            "exams": exams,
            "current_user": current_user,
        }
        return templates.TemplateResponse("exams/schedule.html", context)

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading exam schedule: {str(e)}")
