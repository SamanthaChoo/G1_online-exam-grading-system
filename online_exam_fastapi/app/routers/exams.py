"""Exam management routes."""

from datetime import datetime
from typing import Optional

from app.database import get_session
from app.deps import get_current_user, require_role
from app.models import Course, Exam, User
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

    has_sort = (sort not in (None, "", "start")) or (
        (direction or "asc").lower() != "asc"
    )

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
