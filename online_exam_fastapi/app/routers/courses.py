"""Course management routes."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlmodel import Session, select

from app.database import get_session
from app.deps import get_current_user, require_role
from app.models import Course, CourseLecturer, Enrollment, Exam, Student, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def list_courses(
    request: Request,
    sort: Optional[str] = Query("created"),
    direction: Optional[str] = Query("desc"),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """List courses with optional sorting by column."""
    courses = session.exec(select(Course)).all()
    exam_counts = dict(
        session.exec(select(Exam.course_id, func.count(Exam.id)).group_by(Exam.course_id)).all()
    )
    
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

    context = {
        "request": request,
        "courses": courses_sorted,
        "exam_counts": exam_counts,
        "enrollment_counts": enrollment_counts,
        "course_lecturers": course_lecturers_map,
        "sort": sort,
        "direction": "desc" if is_desc else "asc",
        "has_sort": (sort not in (None, "", "created") or (direction or "desc").lower() != "desc"),
        "current_user": current_user,
    }
    return templates.TemplateResponse("courses/list.html", context)


@router.get("/new")
def new_course_form(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    # Fetch all active lecturers
    lecturers = session.exec(
        select(User).where(User.role == "lecturer", User.is_active == True)
    ).all()
    
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
def create_course(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    lecturer_ids: Optional[list[int]] = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
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

    # Validate lecturer IDs if provided
    lecturer_ids_list = []
    if lecturer_ids:
        if isinstance(lecturer_ids, list):
            lecturer_ids_list = [int(lid) for lid in lecturer_ids if lid]
        else:
            lecturer_ids_list = [int(lecturer_ids)]
        
        # Verify all lecturer IDs are valid lecturers
        valid_lecturers = session.exec(
            select(User).where(
                User.id.in_(lecturer_ids_list),
                User.role == "lecturer",
                User.is_active == True
            )
        ).all()
        if len(valid_lecturers) != len(lecturer_ids_list):
            errors["lecturers"] = "One or more selected lecturers are invalid."

    if errors:
        # Fetch all lecturers for the form
        lecturers = session.exec(
            select(User).where(User.role == "lecturer", User.is_active == True)
        ).all()
        
        context = {
            "request": request,
            "form": {"code": code, "name": name, "description": description or ""},
            "errors": errors,
            "lecturers": lecturers,
            "selected_lecturer_ids": lecturer_ids_list,
            "current_user": current_user,
        }
        return templates.TemplateResponse(
            "courses/form.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    # Create course
    course = Course(code=code_clean, name=name_clean, description=description)
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
        "current_user": current_user,
    }
    return templates.TemplateResponse("courses/enroll.html", context)


@router.post("/{course_id}/enroll")
def enroll_students(
    course_id: int,
    student_ids: Optional[List[int]] = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
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
def edit_course_form(
    course_id: int, 
    request: Request, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """Show edit form for an existing course."""
    course = _get_course(course_id, session)
    
    # Get currently assigned lecturers
    course_lecturers = session.exec(
        select(CourseLecturer).where(CourseLecturer.course_id == course_id)
    ).all()
    selected_lecturer_ids = [cl.lecturer_id for cl in course_lecturers]
    
    # Fetch all active lecturers
    lecturers = session.exec(
        select(User).where(User.role == "lecturer", User.is_active == True)
    ).all()
    
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
def update_course(
    course_id: int,
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    lecturer_ids: Optional[list[int]] = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
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

    # Validate lecturer IDs if provided
    lecturer_ids_list = []
    if lecturer_ids:
        if isinstance(lecturer_ids, list):
            lecturer_ids_list = [int(lid) for lid in lecturer_ids if lid]
        else:
            lecturer_ids_list = [int(lecturer_ids)]
        
        # Verify all lecturer IDs are valid lecturers
        valid_lecturers = session.exec(
            select(User).where(
                User.id.in_(lecturer_ids_list),
                User.role == "lecturer",
                User.is_active == True
            )
        ).all()
        if len(valid_lecturers) != len(lecturer_ids_list):
            errors["lecturers"] = "One or more selected lecturers are invalid."

    if errors:
        # Fetch all lecturers for the form
        lecturers = session.exec(
            select(User).where(User.role == "lecturer", User.is_active == True)
        ).all()
        
        # Get currently assigned lecturers
        course_lecturers = session.exec(
            select(CourseLecturer).where(CourseLecturer.course_id == course_id)
        ).all()
        current_lecturer_ids = [cl.lecturer_id for cl in course_lecturers]
        
        context = {
            "request": request,
            "form": {"code": code, "name": name, "description": description or ""},
            "errors": errors,
            "is_edit": True,
            "course_id": course_id,
            "lecturers": lecturers,
            "selected_lecturer_ids": lecturer_ids_list if lecturer_ids_list else current_lecturer_ids,
            "current_user": current_user,
        }
        return templates.TemplateResponse(
            "courses/form.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    # Update course
    course.code = code_clean
    course.name = name_clean
    course.description = description
    session.add(course)

    # Update lecturer assignments
    existing_assignments = session.exec(
        select(CourseLecturer).where(CourseLecturer.course_id == course_id)
    ).all()
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

