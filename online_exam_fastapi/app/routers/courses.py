"""Course management routes."""

from typing import Optional
import re

from app.database import get_session
from app.deps import require_role, get_current_user
from app.models import Course, CourseLecturer, Enrollment, Exam, Student, User
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlmodel import Session, select

COURSE_CODE_MAX_LENGTH = 20
COURSE_NAME_MAX_LENGTH = 120
COURSE_DESCRIPTION_MAX_LENGTH = 500  # 500 characters max for course description
COURSE_CODE_PATTERN = re.compile(r"^[A-Z0-9\-]+$")

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


ITEMS_PER_PAGE = 10  # Number of items per page for pagination


@router.get("/")
def list_courses(
    request: Request,
    sort: Optional[str] = Query("created"),
    direction: Optional[str] = Query("desc"),
    page: Optional[int] = Query(1, ge=1),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """List courses with optional sorting by column and pagination."""
    courses = session.exec(select(Course)).all()
    exam_counts = dict(session.exec(select(Exam.course_id, func.count(Exam.id)).group_by(Exam.course_id)).all())

    # Get enrollment counts for each course
    enrollment_counts = dict(
        session.exec(select(Enrollment.course_id, func.count(Enrollment.id)).group_by(Enrollment.course_id)).all()
    )

    # Get lecturer assignments for each course
    course_lecturers_map = {}
    course_lecturers = session.exec(select(CourseLecturer)).all()
    for cl in course_lecturers:
        if cl.course_id not in course_lecturers_map:
            course_lecturers_map[cl.course_id] = []
        lecturer = session.get(User, cl.lecturer_id)
        if lecturer:
            course_lecturers_map[cl.course_id].append(lecturer)

    key_map = {
        "code": lambda c: c.code or "",
        "name": lambda c: c.name or "",
        "created": lambda c: c.created_at,
        "exams": lambda c: exam_counts.get(c.id, 0),
        "students": lambda c: enrollment_counts.get(c.id, 0),
    }

    sort_key = key_map.get(sort or "created", key_map["created"])
    is_desc = (direction or "desc").lower() == "desc"

    courses_sorted = sorted(courses, key=sort_key, reverse=is_desc)

    # Pagination
    total_courses = len(courses_sorted)
    total_pages = (total_courses + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_courses > 0 else 1
    page = min(page, total_pages) if total_pages > 0 else 1
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    courses_paginated = courses_sorted[start_idx:end_idx]

    context = {
        "request": request,
        "courses": courses_paginated,
        "exam_counts": exam_counts,
        "enrollment_counts": enrollment_counts,
        "course_lecturers": course_lecturers_map,
        "sort": sort,
        "direction": "desc" if is_desc else "asc",
        "has_sort": (sort not in (None, "", "created") or (direction or "desc").lower() != "desc"),
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total_courses,
        "items_per_page": ITEMS_PER_PAGE,
        "current_user": current_user,
    }
    return templates.TemplateResponse("courses/list.html", context)


@router.get("/student")
def student_course_list(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
):
    """List courses that the current student is enrolled in."""
    # Verify user is logged in
    if not current_user:
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/auth/login", status_code=303)

    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="This page is only accessible to students")

    # Get student_id from user
    student_id = current_user.student_id
    if student_id is None:
        # Try to find student by user_id
        student = session.exec(select(Student).where(Student.user_id == current_user.id)).first()
        student_id = student.id if student else None

    if student_id is None:
        # Student record not found
        context = {
            "request": request,
            "current_user": current_user,
            "error": "No student record found. Please contact administrator.",
            "courses": [],
            "enrollments": [],
            "exam_counts": {},
            "course_lecturers": {},
            "student": None,
        }
        return templates.TemplateResponse("courses/student_list.html", context)

    # Get all enrollments for this student
    enrollments = session.exec(select(Enrollment).where(Enrollment.student_id == student_id)).all()

    # Get course IDs from enrollments
    course_ids = [enrollment.course_id for enrollment in enrollments]

    # Get courses
    courses = []
    if course_ids:
        courses = session.exec(select(Course).where(Course.id.in_(course_ids))).all()

    # Get exam counts for each course
    exam_counts = {}
    if course_ids:
        exam_counts = dict(
            session.exec(
                select(Exam.course_id, func.count(Exam.id))
                .where(Exam.course_id.in_(course_ids))
                .group_by(Exam.course_id)
            ).all()
        )

    # Get lecturers for each course
    course_lecturers_map = {}
    if course_ids:
        course_lecturers = session.exec(select(CourseLecturer).where(CourseLecturer.course_id.in_(course_ids))).all()
        for cl in course_lecturers:
            if cl.course_id not in course_lecturers_map:
                course_lecturers_map[cl.course_id] = []
            lecturer = session.get(User, cl.lecturer_id)
            if lecturer:
                course_lecturers_map[cl.course_id].append(lecturer)

    # Sort courses by name
    courses_sorted = sorted(courses, key=lambda c: c.name)

    # Get student info
    student = session.get(Student, student_id)

    context = {
        "request": request,
        "current_user": current_user,
        "courses": courses_sorted,
        "enrollments": enrollments,
        "exam_counts": exam_counts,
        "course_lecturers": course_lecturers_map,
        "student": student,
    }
    return templates.TemplateResponse("courses/student_list.html", context)


@router.get("/new")
def new_course_form(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    # Fetch all active lecturers
    lecturers = session.exec(select(User).where(User.role == "lecturer", User.is_active.is_(True))).all()

    context = {
        "request": request,
        "form": None,
        "errors": {},
        "is_edit": False,
        "lecturers": lecturers,
        "selected_lecturer_ids": [],
        "current_user": current_user,
    }
    return templates.TemplateResponse("courses/form.html", context)


@router.post("/new")
async def create_course(
    request: Request,
    code: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    # Get lecturer_ids from form - can be single value or multiple
    # HTML <select multiple> sends multiple fields with same name when multiple selected,
    # or single value when one selected. Use getlist() to handle both.
    # NOTE: We read from request.form() directly to avoid FastAPI trying to parse it as a list
    # when only one value is selected (which would cause a validation error)
    try:
        form_data = await request.form()
        lecturer_ids_raw = form_data.getlist("lecturer_ids")
    except (RuntimeError, AttributeError, TypeError):
        # If request.form() is not available (e.g., in tests with mock request), use empty list
        lecturer_ids_raw = []

    code_clean = (code or "").strip().upper()
    name_clean = (name or "").strip()

    errors = {}

    if not code_clean:
        errors["code"] = "Course code is required."
    elif len(code_clean) > COURSE_CODE_MAX_LENGTH:
        errors["code"] = f"Course code must be at most {COURSE_CODE_MAX_LENGTH} characters."
    elif not COURSE_CODE_PATTERN.match(code_clean):
        errors["code"] = "Course code can only contain letters, numbers, or hyphens."

    if not name_clean:
        errors["name"] = "Course name is required."
    elif len(name_clean) > COURSE_NAME_MAX_LENGTH:
        errors["name"] = f"Course name must be at most {COURSE_NAME_MAX_LENGTH} characters."

    # Description validation (optional field, but has max length if provided)
    description_clean = (description or "").strip() if description else ""
    if description_clean and len(description_clean) > COURSE_DESCRIPTION_MAX_LENGTH:
        errors["description"] = f"Course description must be at most {COURSE_DESCRIPTION_MAX_LENGTH} characters."

    # Check for duplicate code (case-insensitive)
    if code_clean and session.exec(select(Course).where(Course.code == code_clean)).first():
        errors["code"] = "This course code is already in use. Please choose another."

    # Normalize lecturer_ids: getlist() always returns a list, even if empty or single value
    lecturer_ids_list = []
    if lecturer_ids_raw:
        try:
            lecturer_ids_list = [int(lid) for lid in lecturer_ids_raw if lid and str(lid).strip()]
        except (ValueError, TypeError):
            pass

        # Verify all lecturer IDs are valid lecturers
        valid_lecturers = session.exec(
            select(User).where(
                User.id.in_(lecturer_ids_list),
                User.role == "lecturer",
                User.is_active.is_(True),
            )
        ).all()
        if len(valid_lecturers) != len(lecturer_ids_list):
            errors["lecturers"] = "One or more selected lecturers are invalid."

    if errors:
        # Fetch all lecturers for the form
        lecturers = session.exec(select(User).where(User.role == "lecturer", User.is_active.is_(True))).all()

        context = {
            "request": request,
            "form": {
                "code": code or "",
                "name": name or "",
                "description": description or "",
            },
            "errors": errors,
            "lecturers": lecturers,
            "selected_lecturer_ids": lecturer_ids_list,
            "current_user": current_user,
        }
        return templates.TemplateResponse("courses/form.html", context, status_code=status.HTTP_400_BAD_REQUEST)

    # Create course
    course = Course(code=code_clean, name=name_clean, description=description_clean or None)
    session.add(course)
    session.commit()
    session.refresh(course)

    # Assign lecturers
    if lecturer_ids_list:
        for lecturer_id in lecturer_ids_list:
            course_lecturer = CourseLecturer(course_id=course.id, lecturer_id=lecturer_id)
            session.add(course_lecturer)
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
    page: Optional[int] = Query(1, ge=1),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """Enrollment management view.

    - Left: currently enrolled students
    - Right: available students that are not yet enrolled (optionally filtered by search query)

    Note: Students are fetched from the Student database table, not from User table.
    """
    course = _get_course(course_id, session)
    enrollments = session.exec(select(Enrollment).where(Enrollment.course_id == course_id)).all()
    enrolled_ids = {enrollment.student_id for enrollment in enrollments}

    # Fetch all students from the Student database table
    stmt = select(Student)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            (Student.name.ilike(pattern)) | (Student.email.ilike(pattern)) | (Student.matric_no.ilike(pattern))
        )
    stmt = stmt.order_by(Student.name)
    students = session.exec(stmt).all()

    enrolled_students = [s for s in students if s.id in enrolled_ids]
    available_students = [s for s in students if s.id not in enrolled_ids]

    # Pagination for available students only (enrolled students are always shown)
    total_available = len(available_students)
    total_pages = (total_available + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_available > 0 else 1
    page = min(page, total_pages) if total_pages > 0 else 1
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    available_students_paginated = available_students[start_idx:end_idx]

    context = {
        "request": request,
        "course": course,
        "q": q or "",
        "enrolled_students": enrolled_students,  # Always show all enrolled
        "available_students": available_students_paginated,  # Paginated
        "enrolled_ids": enrolled_ids,
        "enrolled_count": len(enrolled_ids),
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total_available,  # Total available students
        "items_per_page": ITEMS_PER_PAGE,
        "current_user": current_user,
    }
    return templates.TemplateResponse("courses/enroll.html", context)


@router.post("/{course_id}/enroll")
async def enroll_students(
    course_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    course = _get_course(course_id, session)

    # Get student_ids from form - can be single value or multiple
    # HTML <select multiple> sends multiple fields with same name when multiple selected,
    # or single value when one selected. Use getlist() to handle both.
    try:
        form_data = await request.form()
        student_ids_raw = form_data.getlist("student_ids")
    except (RuntimeError, AttributeError, TypeError):
        # If request.form() is not available (e.g., in tests with mock request), use empty list
        student_ids_raw = []

    # Convert to integers and create set
    selected_ids = set()
    for sid in student_ids_raw:
        try:
            selected_ids.add(int(sid))
        except (ValueError, TypeError):
            continue  # Skip invalid values
    existing_enrollments = session.exec(select(Enrollment).where(Enrollment.course_id == course_id)).all()

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
def edit_course_form(
    course_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """Show edit form for an existing course."""
    course = _get_course(course_id, session)

    # Get currently assigned lecturers
    course_lecturers = session.exec(select(CourseLecturer).where(CourseLecturer.course_id == course_id)).all()
    selected_lecturer_ids = [cl.lecturer_id for cl in course_lecturers]

    # Fetch all active lecturers
    lecturers = session.exec(select(User).where(User.role == "lecturer", User.is_active.is_(True))).all()

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
        "lecturers": lecturers,
        "selected_lecturer_ids": selected_lecturer_ids,
        "current_user": current_user,
    }
    return templates.TemplateResponse("courses/form.html", context)


@router.post("/{course_id}/edit")
async def update_course(
    course_id: int,
    request: Request,
    code: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    course = _get_course(course_id, session)

    # Get lecturer_ids from form - handle both single and multiple values
    # NOTE: We read from request.form() directly to avoid FastAPI trying to parse it as a list
    # when only one value is selected (which would cause a validation error)
    try:
        form_data = await request.form()
        lecturer_ids_raw = form_data.getlist("lecturer_ids")
    except (RuntimeError, AttributeError, TypeError):
        # If request.form() is not available (e.g., in tests with mock request), use empty list
        lecturer_ids_raw = []

    # Normalize lecturer_ids: getlist() always returns a list
    lecturer_ids_list = []
    if lecturer_ids_raw:
        try:
            lecturer_ids_list = [int(lid) for lid in lecturer_ids_raw if lid and str(lid).strip()]
        except (ValueError, TypeError):
            pass

    code_clean = (code or "").strip().upper()
    name_clean = (name or "").strip()
    errors = {}

    if not code_clean:
        errors["code"] = "Course code is required."
    elif len(code_clean) > COURSE_CODE_MAX_LENGTH:
        errors["code"] = f"Course code must be at most {COURSE_CODE_MAX_LENGTH} characters."
    elif not COURSE_CODE_PATTERN.match(code_clean):
        errors["code"] = "Course code can only contain letters, numbers, or hyphens."

    if not name_clean:
        errors["name"] = "Course name is required."
    elif len(name_clean) > COURSE_NAME_MAX_LENGTH:
        errors["name"] = f"Course name must be at most {COURSE_NAME_MAX_LENGTH} characters."

    # Description validation (optional field, but has max length if provided)
    description_clean = (description or "").strip() if description else ""
    if description_clean and len(description_clean) > COURSE_DESCRIPTION_MAX_LENGTH:
        errors["description"] = f"Course description must be at most {COURSE_DESCRIPTION_MAX_LENGTH} characters."

    # Ensure course code is unique across other courses
    if code_clean:
        existing_course = session.exec(select(Course).where(Course.code == code_clean, Course.id != course_id)).first()
        if existing_course:
            errors["code"] = "This course code is already used by another course."

    if errors:
        # Fetch all lecturers for the form
        lecturers = session.exec(select(User).where(User.role == "lecturer", User.is_active.is_(True))).all()

        # Get currently assigned lecturers
        course_lecturers = session.exec(select(CourseLecturer).where(CourseLecturer.course_id == course_id)).all()
        current_lecturer_ids = [cl.lecturer_id for cl in course_lecturers]

        context = {
            "request": request,
            "form": {
                "code": code_clean,
                "name": name_clean,
                "description": description_clean or "",
            },
            "errors": errors,
            "is_edit": True,
            "course_id": course_id,
            "lecturers": lecturers,
            "selected_lecturer_ids": (lecturer_ids_list if lecturer_ids_list else current_lecturer_ids),
            "current_user": current_user,
        }
        return templates.TemplateResponse("courses/form.html", context, status_code=status.HTTP_400_BAD_REQUEST)

    # Update course
    course.code = code_clean
    course.name = name_clean
    course.description = description_clean or None
    session.add(course)

    # Update lecturer assignments
    existing_assignments = session.exec(select(CourseLecturer).where(CourseLecturer.course_id == course_id)).all()
    existing_lecturer_ids = {cl.lecturer_id for cl in existing_assignments}
    new_lecturer_ids = set(lecturer_ids_list)

    # Remove unassigned lecturers
    for assignment in existing_assignments:
        if assignment.lecturer_id not in new_lecturer_ids:
            session.delete(assignment)

    # Add new lecturer assignments
    for lecturer_id in new_lecturer_ids - existing_lecturer_ids:
        course_lecturer = CourseLecturer(course_id=course.id, lecturer_id=lecturer_id)
        session.add(course_lecturer)

    session.commit()

    return RedirectResponse(url="/courses/", status_code=status.HTTP_303_SEE_OTHER)
