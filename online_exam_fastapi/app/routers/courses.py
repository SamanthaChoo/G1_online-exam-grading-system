"""Course management routes."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlmodel import Session, select

from app.database import get_session
from app.models import Course, Enrollment, Exam, Student

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def list_courses(
    request: Request,
    sort: Optional[str] = Query("created"),
    direction: Optional[str] = Query("desc"),
    session: Session = Depends(get_session),
):
    """List courses with optional sorting by column."""
    courses = session.exec(select(Course)).all()
    exam_counts = dict(
        session.exec(select(Exam.course_id, func.count(Exam.id)).group_by(Exam.course_id)).all()
    )

    key_map = {
        "code": lambda c: c.code or "",
        "name": lambda c: c.name or "",
        "created": lambda c: c.created_at,
        "exams": lambda c: exam_counts.get(c.id, 0),
    }

    sort_key = key_map.get(sort or "created", key_map["created"])
    is_desc = (direction or "desc").lower() == "desc"

    courses_sorted = sorted(courses, key=sort_key, reverse=is_desc)

    context = {
        "request": request,
        "courses": courses_sorted,
        "exam_counts": exam_counts,
        "sort": sort,
        "direction": "desc" if is_desc else "asc",
        "has_sort": (sort not in (None, "", "created") or (direction or "desc").lower() != "desc"),
    }
    return templates.TemplateResponse("courses/list.html", context)


@router.get("/new")
def new_course_form(request: Request):
    context = {
        "request": request,
        "form": None,
        "errors": {},
        "is_edit": False,
    }
    return templates.TemplateResponse("courses/form.html", context)


@router.post("/new")
def create_course(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    code_clean = code.strip()
    name_clean = name.strip()

    errors = {}

    if not code_clean:
        errors["code"] = "Course code is required."
    if not name_clean:
        errors["name"] = "Course name is required."

    # Check for duplicate code (case-insensitive)
    if code_clean and session.exec(
        select(Course).where(Course.code == code_clean)
    ).first():
        errors["code"] = "This course code is already in use. Please choose another."

    if errors:
        context = {
            "request": request,
            "form": {"code": code, "name": name, "description": description or ""},
            "errors": errors,
        }
        return templates.TemplateResponse(
            "courses/form.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    course = Course(code=code_clean, name=name_clean, description=description)
    session.add(course)
    session.commit()
    return RedirectResponse(url="/courses/", status_code=status.HTTP_303_SEE_OTHER)


def _get_course(course_id: int, session: Session) -> Course:
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.get("/{course_id}/enroll")
def enroll_form(
    course_id: int,
    request: Request,
    q: Optional[str] = Query(None, description="Search students by name, email, or matric"),
    session: Session = Depends(get_session),
):
    """Enrollment management view.

    - Left: currently enrolled students
    - Right: available students that are not yet enrolled (optionally filtered by search query)
    """
    course = _get_course(course_id, session)
    enrollments = session.exec(select(Enrollment).where(Enrollment.course_id == course_id)).all()
    enrolled_ids = {enrollment.student_id for enrollment in enrollments}

    stmt = select(Student)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            (Student.name.ilike(pattern))
            | (Student.email.ilike(pattern))
            | (Student.matric_no.ilike(pattern))
        )
    stmt = stmt.order_by(Student.name)
    students = session.exec(stmt).all()

    enrolled_students = [s for s in students if s.id in enrolled_ids]
    available_students = [s for s in students if s.id not in enrolled_ids]

    context = {
        "request": request,
        "course": course,
        "q": q or "",
        "enrolled_students": enrolled_students,
        "available_students": available_students,
        "enrolled_ids": enrolled_ids,
        "enrolled_count": len(enrolled_ids),
    }
    return templates.TemplateResponse("courses/enroll.html", context)


@router.post("/{course_id}/enroll")
def enroll_students(
    course_id: int,
    student_ids: Optional[List[int]] = Form(None),
    session: Session = Depends(get_session),
):
    course = _get_course(course_id, session)
    selected_ids = set(map(int, student_ids)) if student_ids else set()
    existing_enrollments = session.exec(
        select(Enrollment).where(Enrollment.course_id == course_id)
    ).all()

    existing_ids = {enrollment.student_id for enrollment in existing_enrollments}

    # Remove unenrolled students
    for enrollment in existing_enrollments:
        if enrollment.student_id not in selected_ids:
            session.delete(enrollment)

    # Add new enrollments
    for student_id in selected_ids - existing_ids:
        session.add(Enrollment(course_id=course.id, student_id=student_id))

    session.commit()
    return RedirectResponse(url="/courses/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{course_id}/edit")
def edit_course_form(course_id: int, request: Request, session: Session = Depends(get_session)):
    """Show edit form for an existing course."""
    course = _get_course(course_id, session)
    form = {
        "code": course.code,
        "name": course.name,
        "description": course.description or "",
    }
    context = {
        "request": request,
        "form": form,
        "errors": {},
        "is_edit": True,
        "course_id": course_id,
    }
    return templates.TemplateResponse("courses/form.html", context)


@router.post("/{course_id}/edit")
def update_course(
    course_id: int,
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    course = _get_course(course_id, session)

    code_clean = code.strip()
    name_clean = name.strip()
    errors = {}

    if not code_clean:
        errors["code"] = "Course code is required."
    if not name_clean:
        errors["name"] = "Course name is required."

    # Ensure course code is unique across other courses
    if code_clean:
        existing = session.exec(
            select(Course).where(Course.code == code_clean, Course.id != course_id)
        ).first()
        if existing:
            errors["code"] = "This course code is already used by another course."

    if errors:
        context = {
            "request": request,
            "form": {"code": code, "name": name, "description": description or ""},
            "errors": errors,
            "is_edit": True,
            "course_id": course_id,
        }
        return templates.TemplateResponse(
            "courses/form.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    course.code = code_clean
    course.name = name_clean
    course.description = description
    session.add(course)
    session.commit()

    return RedirectResponse(url="/courses/", status_code=status.HTTP_303_SEE_OTHER)

