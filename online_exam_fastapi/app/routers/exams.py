"""Exam management routes."""

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi import status as http_status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from datetime import datetime
from typing import Optional
import json

from app.database import get_session
from app.deps import get_current_user, require_role
from app.models import (
    Course,
    Exam,
    User,
    Enrollment,
    MCQQuestion,
    MCQAnswer,
    MCQResult,
    Student,
    ExamActivityLog,
    CourseLecturer,
)

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


@router.get("/schedule/student/{student_id}")
def student_exam_schedule(
    student_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    """View exam schedule for a specific student."""
    # Get all courses student is enrolled in
    enrollments = session.exec(select(Enrollment).where(Enrollment.student_id == student_id)).all()
    course_ids = [e.course_id for e in enrollments]
    # Get all exams for these courses
    now = datetime.now()
    exams = session.exec(select(Exam).where(Exam.course_id.in_(course_ids))).all() if course_ids else []
    # Compute exam status
    exam_list = []
    for exam in exams:
        if not exam.start_time or not exam.end_time:
            status = "unscheduled"
        elif now < exam.start_time:
            mins_to_start = (exam.start_time - now).total_seconds() / 60
            if mins_to_start > 30:
                status = "upcoming"
            else:
                status = "starting soon"
        elif exam.start_time <= now <= exam.end_time:
            status = "ongoing"
        else:
            status = "ended"
        exam_list.append({"exam": exam, "status": status})
    student = session.get(Student, student_id)
    context = {"request": request, "exams": exam_list, "student": student, "current_user": current_user}
    return templates.TemplateResponse("exams/schedule.html", context)


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
    exam = session.get(Exam, exam_id)
    student = session.get(Student, student_id)

    # Enforce single attempt: if result already exists, redirect to finished page.
    if student and exam and _has_mcq_result(session, exam_id, student_id):
        return RedirectResponse(
            url="/exams/exam_finished",
            status_code=http_status.HTTP_303_SEE_OTHER,
        )

    # Get MCQ questions
    questions = session.exec(select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)).all()
    # Get any existing answers
    answers = session.exec(
        select(MCQAnswer).where(
            MCQAnswer.exam_id == exam_id,
            MCQAnswer.student_id == student_id,
        )
    ).all()
    answer_map = {a.question_id: a.selected_option for a in answers}
    context = {
        "request": request,
        "exam": exam,
        "student": student,
        "questions": questions,
        "answer_map": answer_map,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/join_exam.html", context)


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
        return {"status": "error", "message": "student_id and activity_type are required"}

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
    data = await request.json()
    student_id = data.get("student_id")
    answers = data.get("answers", {})
    for qid, selected in answers.items():
        qid = int(qid)
        answer = session.exec(
            select(MCQAnswer).where(
                MCQAnswer.exam_id == exam_id, MCQAnswer.student_id == student_id, MCQAnswer.question_id == qid
            )
        ).first()
        if answer:
            answer.selected_option = selected
            answer.saved_at = datetime.utcnow()
            session.add(answer)
        else:
            session.add(MCQAnswer(student_id=student_id, exam_id=exam_id, question_id=qid, selected_option=selected))
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
                MCQAnswer.exam_id == exam_id, MCQAnswer.student_id == student_id, MCQAnswer.question_id == qid
            )
        ).first()
        if answer:
            answer.selected_option = selected
            answer.saved_at = datetime.utcnow()
            session.add(answer)
        else:
            session.add(MCQAnswer(student_id=student_id, exam_id=exam_id, question_id=qid, selected_option=selected))
    session.commit()
    # Auto-grade
    questions = session.exec(select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)).all()
    correct = 0
    for q in questions:
        ans = session.exec(
            select(MCQAnswer).where(
                MCQAnswer.exam_id == exam_id, MCQAnswer.student_id == student_id, MCQAnswer.question_id == q.id
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
    context = {"request": request, "exam": exam, "questions": questions, "current_user": current_user}
    return templates.TemplateResponse("exams/mcq_list.html", context)


@router.get("/{exam_id}/mcq/new")
def new_mcq_form(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    exam = session.get(Exam, exam_id)
    context = {"request": request, "exam": exam, "form": None, "errors": {}, "current_user": current_user}
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
    context = {"request": request, "mcq": mcq, "exam": exam, "form": None, "errors": {}, "current_user": current_user}
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


# MCQ Management Menu: Select Exam for MCQ CRUD
@router.get("/mcq/menu")
def mcq_menu(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    exams = session.exec(select(Exam)).all()
    context = {"request": request, "exams": exams, "current_user": current_user}
    return templates.TemplateResponse("exams/mcq_menu.html", context)


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


@router.get("/course/{course_id}/student")
def student_exams_for_course(
    course_id: int,
    request: Request,
    sort: Optional[str] = Query("start"),
    direction: Optional[str] = Query("asc"),
    page: Optional[int] = Query(1, ge=1),
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List exams for a course - student view only (read-only, no edit buttons)."""
    # Verify user is logged in and is a student
    if not current_user:
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/auth/login", status_code=303)

    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="This page is only accessible to students")

    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Verify student is enrolled in this course
    student_id = current_user.student_id
    if student_id is None:
        student = session.exec(select(Student).where(Student.user_id == current_user.id)).first()
        student_id = student.id if student else None

    if student_id is None:
        raise HTTPException(status_code=403, detail="Student record not found")

    enrollment = session.exec(
        select(Enrollment).where(Enrollment.student_id == student_id, Enrollment.course_id == course_id)
    ).first()

    if not enrollment:
        raise HTTPException(status_code=403, detail="You are not enrolled in this course")

    # Get exams for this course
    exams = session.exec(select(Exam).where(Exam.course_id == course_id)).all()

    # Compute exam status for each exam
    now = datetime.now()
    exam_list = []
    for exam in exams:
        if not exam.start_time or not exam.end_time:
            status = "unscheduled"
        elif now < exam.start_time:
            mins_to_start = (exam.start_time - now).total_seconds() / 60
            if mins_to_start > 30:
                status = "upcoming"
            else:
                status = "starting soon"
        elif exam.start_time <= now <= exam.end_time:
            status = "ongoing"
        else:
            status = "ended"

        # Check if student has already completed this exam
        has_result = _has_mcq_result(session, exam.id, student_id)
        exam_list.append({"exam": exam, "status": status, "has_result": has_result})

    # Sorting
    key_map = {
        "title": lambda e: e["exam"].title or "",
        "subject": lambda e: e["exam"].subject or "",
        "start": lambda e: e["exam"].start_time or datetime.max,
        "end": lambda e: e["exam"].end_time or datetime.max,
        "duration": lambda e: e["exam"].duration_minutes or 0,
        "status": lambda e: e["status"],
    }

    sort_key = key_map.get(sort or "start", key_map["start"])
    is_desc = (direction or "asc").lower() == "desc"
    exams_sorted = sorted(exam_list, key=sort_key, reverse=is_desc)

    # Pagination
    total_exams = len(exams_sorted)
    total_pages = (total_exams + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_exams > 0 else 1
    page = min(page, total_pages) if total_pages > 0 else 1
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    exams_paginated = exams_sorted[start_idx:end_idx]

    has_sort = (sort not in (None, "", "start")) or ((direction or "asc").lower() != "asc")

    student = session.get(Student, student_id)

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
        "student": student,
    }
    return templates.TemplateResponse("exams/list_by_course_student.html", context)


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
    """List all exams associated with a specific course - lecturer/admin view with edit buttons."""
    # Redirect students to the student-specific route
    if current_user and current_user.role == "student":
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url=f"/exams/course/{course_id}/student", status_code=303)

    # Require lecturer or admin role
    if not current_user or current_user.role not in ["lecturer", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Lecturer or admin role required.")

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
def exam_finished(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    context = {"request": request, "current_user": current_user}
    return templates.TemplateResponse("exams/exam_finished.html", context)


@router.get("/{exam_id}")
def exam_detail(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    """View exam details. Students can view, lecturers/admins can view and edit."""
    exam = _get_exam(exam_id, session)
    course = session.get(Course, exam.course_id) if exam.course_id else None

    # If student, verify they are enrolled in the course
    if current_user and current_user.role == "student":
        student_id = current_user.student_id
        if student_id is None:
            student = session.exec(select(Student).where(Student.user_id == current_user.id)).first()
            student_id = student.id if student else None

        if student_id and exam.course_id:
            enrollment = session.exec(
                select(Enrollment).where(Enrollment.student_id == student_id, Enrollment.course_id == exam.course_id)
            ).first()
            if not enrollment:
                raise HTTPException(status_code=403, detail="You are not enrolled in this course")

    context = {
        "request": request,
        "exam": exam,
        "course": course,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/detail.html", context)


@router.get("/{exam_id}/view")
def exam_detail_student(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Alias for exam detail page - redirects to main detail page."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url=f"/exams/{exam_id}", status_code=303)


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


# ===================== EXAM SECURITY: ACTIVITY LOGGING & ANALYTICS =====================


@router.get("/{exam_id}/activity-logs")
def view_activity_logs(
    exam_id: int,
    request: Request,
    student_id: Optional[int] = Query(None),
    activity_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    page: Optional[int] = Query(1, ge=1),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """View activity logs for a specific exam with filtering options."""
    exam = _get_exam(exam_id, session)

    # Check if lecturer has access to this exam's course
    if current_user.role == "lecturer":
        course_lecturer = session.exec(
            select(CourseLecturer).where(
                CourseLecturer.lecturer_id == current_user.id, CourseLecturer.course_id == exam.course_id
            )
        ).first()
        if not course_lecturer and not current_user.role == "admin":
            raise HTTPException(status_code=403, detail="You don't have access to this exam's activity logs")

    # Build query
    query = select(ExamActivityLog).where(ExamActivityLog.exam_id == exam_id)

    if student_id:
        query = query.where(ExamActivityLog.student_id == student_id)
    if activity_type:
        query = query.where(ExamActivityLog.activity_type == activity_type)
    if severity:
        query = query.where(ExamActivityLog.severity == severity)

    query = query.order_by(ExamActivityLog.timestamp.desc())

    # Get all logs
    all_logs = session.exec(query).all()

    # Get students and exam info for display
    students = {s.id: s for s in session.exec(select(Student)).all()}

    # Calculate statistics
    stats = {
        "total_activities": len(all_logs),
        "by_severity": {"low": 0, "medium": 0, "high": 0},
        "by_type": {},
        "by_student": {},
    }

    for log in all_logs:
        # Count by severity
        stats["by_severity"][log.severity] = stats["by_severity"].get(log.severity, 0) + 1

        # Count by type
        stats["by_type"][log.activity_type] = stats["by_type"].get(log.activity_type, 0) + 1

        # Count by student
        student_name = students.get(log.student_id, Student(name="Unknown")).name
        if student_name not in stats["by_student"]:
            stats["by_student"][student_name] = {"total": 0, "high": 0, "medium": 0, "low": 0}
        stats["by_student"][student_name]["total"] += 1
        stats["by_student"][student_name][log.severity] += 1

    # Pagination
    total_logs = len(all_logs)
    total_pages = (total_logs + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_logs > 0 else 1
    page = min(page, total_pages) if total_pages > 0 else 1
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    logs_paginated = all_logs[start_idx:end_idx]

    # Parse metadata for display
    logs_with_metadata = []
    for log in logs_paginated:
        metadata_obj = None
        if log.activity_metadata:
            try:
                metadata_obj = json.loads(log.activity_metadata)
            except (json.JSONDecodeError, ValueError):
                metadata_obj = {"raw": log.activity_metadata}
        logs_with_metadata.append({"log": log, "student": students.get(log.student_id), "metadata": metadata_obj})

    # Get unique activity types and severities for filter dropdowns
    activity_types = sorted(set(log.activity_type for log in all_logs))
    severities = ["low", "medium", "high"]
    student_list = [{"id": s.id, "name": s.name} for s in students.values()]

    context = {
        "request": request,
        "exam": exam,
        "logs": logs_with_metadata,
        "stats": stats,
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total_logs,
        "items_per_page": ITEMS_PER_PAGE,
        "filters": {
            "student_id": student_id,
            "activity_type": activity_type,
            "severity": severity,
        },
        "activity_types": activity_types,
        "severities": severities,
        "students": student_list,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/activity_logs.html", context)


@router.get("/{exam_id}/activity-analytics")
def view_activity_analytics(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """View activity analytics and flagged students for an exam."""
    exam = _get_exam(exam_id, session)

    # Check if lecturer has access to this exam's course
    if current_user.role == "lecturer":
        course_lecturer = session.exec(
            select(CourseLecturer).where(
                CourseLecturer.lecturer_id == current_user.id, CourseLecturer.course_id == exam.course_id
            )
        ).first()
        if not course_lecturer and not current_user.role == "admin":
            raise HTTPException(status_code=403, detail="You don't have access to this exam's analytics")

    # Get all activity logs for this exam
    logs = session.exec(select(ExamActivityLog).where(ExamActivityLog.exam_id == exam_id)).all()

    # Get students
    students = {s.id: s for s in session.exec(select(Student)).all()}

    # Calculate activity scores and flag students
    # Scoring: low=1, medium=3, high=10
    SCORE_WEIGHTS = {"low": 1, "medium": 3, "high": 10}
    FLAG_THRESHOLD = 20  # Flag if score >= 20

    student_analytics = {}

    for log in logs:
        if log.student_id not in student_analytics:
            student_analytics[log.student_id] = {
                "student": students.get(log.student_id),
                "total_activities": 0,
                "score": 0,
                "by_type": {},
                "by_severity": {"low": 0, "medium": 0, "high": 0},
                "flagged": False,
                "last_activity": log.timestamp,
            }

        analytics = student_analytics[log.student_id]
        analytics["total_activities"] += 1
        analytics["score"] += SCORE_WEIGHTS.get(log.severity, 1)
        analytics["by_severity"][log.severity] += 1
        analytics["by_type"][log.activity_type] = analytics["by_type"].get(log.activity_type, 0) + 1

        if log.timestamp > analytics["last_activity"]:
            analytics["last_activity"] = log.timestamp

        if analytics["score"] >= FLAG_THRESHOLD:
            analytics["flagged"] = True

    # Sort by score (highest first)
    analytics_list = sorted(student_analytics.values(), key=lambda x: x["score"], reverse=True)

    # Get flagged students
    flagged_students = [a for a in analytics_list if a["flagged"]]

    # Overall statistics
    overall_stats = {
        "total_students_with_activities": len(student_analytics),
        "flagged_students_count": len(flagged_students),
        "total_activities": len(logs),
        "average_score": sum(a["score"] for a in analytics_list) / len(analytics_list) if analytics_list else 0,
        "highest_score": analytics_list[0]["score"] if analytics_list else 0,
    }

    # Prepare analytics data for JSON serialization (for charts)
    analytics_json = []
    for a in analytics_list:
        student_data = None
        if a["student"]:
            student_data = {
                "id": a["student"].id,
                "name": a["student"].name,
                "matric_no": a["student"].matric_no if hasattr(a["student"], "matric_no") else None,
            }
        analytics_json.append(
            {
                "student_id": None if not a["student"] else a["student"].id,
                "student": student_data,
                "score": a["score"],
                "total_activities": a["total_activities"],
                "by_type": a["by_type"],
                "by_severity": a["by_severity"],
                "flagged": a["flagged"],
                "last_activity": a["last_activity"].isoformat() if a["last_activity"] else None,
            }
        )

    context = {
        "request": request,
        "exam": exam,
        "analytics": analytics_list,
        "analytics_json": analytics_json,  # JSON-serializable version for charts
        "flagged_students": flagged_students,
        "overall_stats": overall_stats,
        "flag_threshold": FLAG_THRESHOLD,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/activity_analytics.html", context)
