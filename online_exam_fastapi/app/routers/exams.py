"""Exam management routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status as http_status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session
from app.deps import get_current_user, require_role
from app.models import Course, Exam, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

STATUS_OPTIONS = ["draft", "scheduled", "completed"]


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _get_exam(exam_id: int, session: Session) -> Exam:
    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


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
def create_exam(
    request: Request,
    title: str = Form(...),
    subject: str = Form(...),
    duration_minutes: str = Form(...),
    course_id: str = Form(...),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    instructions: Optional[str] = Form(None),
    status: str = Form("draft"),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    errors: dict[str, str] = {}

    title_clean = title.strip()
    subject_clean = subject.strip()
    instructions_clean = (instructions or "").strip()

    # Required text fields
    if not title_clean:
        errors["title"] = "Exam title is required."
    if not subject_clean:
        errors["subject"] = "Exam subject is required."

    # Duration validation
    try:
        duration_value = int(duration_minutes)
        if duration_value <= 0:
            errors["duration_minutes"] = "Duration must be greater than zero."
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
        except ValueError:
            start_dt = None
            errors["start_time"] = "Start time format is invalid."

    if not end_time:
        errors["end_time"] = "Exam end time is required."
        end_dt = None
    else:
        try:
            end_dt = _parse_datetime(end_time)
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
            "title": title,
            "subject": subject,
            "duration_minutes": duration_minutes,
            "course_id": course_id,
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
        return templates.TemplateResponse(
            "exams/form.html", context, status_code=http_status.HTTP_400_BAD_REQUEST
        )

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
    return RedirectResponse(
        url=f"/exams/{exam.id}", status_code=http_status.HTTP_303_SEE_OTHER
    )


@router.get("/course/{course_id}")
def exams_for_course(
    course_id: int,
    request: Request,
    sort: Optional[str] = Query("start"),
    direction: Optional[str] = Query("asc"),
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List all exams associated with a specific course, with optional sorting."""
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

    has_sort = (sort not in (None, "", "start")) or (
        (direction or "asc").lower() != "asc"
    )

    context = {
        "request": request,
        "course": course,
        "exams": exams_sorted,
        "sort": sort,
        "direction": "desc" if is_desc else "asc",
        "has_sort": has_sort,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/list_by_course.html", context)


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
def update_exam(
    exam_id: int,
    request: Request,
    title: str = Form(...),
    subject: str = Form(...),
    duration_minutes: str = Form(...),
    course_id: str = Form(...),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    instructions: Optional[str] = Form(None),
    status: str = Form("draft"),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    exam = _get_exam(exam_id, session)

    errors: dict[str, str] = {}

    title_clean = title.strip()
    subject_clean = subject.strip()
    instructions_clean = (instructions or "").strip()

    if not title_clean:
        errors["title"] = "Exam title is required."
    if not subject_clean:
        errors["subject"] = "Exam subject is required."

    try:
        duration_value = int(duration_minutes)
        if duration_value <= 0:
            errors["duration_minutes"] = "Duration must be greater than zero."
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
        except ValueError:
            start_dt = None
            errors["start_time"] = "Start time format is invalid."

    if not end_time:
        errors["end_time"] = "Exam end time is required."
        end_dt = None
    else:
        try:
            end_dt = _parse_datetime(end_time)
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
            "title": title,
            "subject": subject,
            "duration_minutes": duration_minutes,
            "course_id": course_id,
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
        return templates.TemplateResponse(
            "exams/form.html", context, status_code=http_status.HTTP_400_BAD_REQUEST
        )

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

    return RedirectResponse(
        url=f"/exams/{exam.id}", status_code=http_status.HTTP_303_SEE_OTHER
    )

