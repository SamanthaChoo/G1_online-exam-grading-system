"""Admin routes for managing users and their roles."""

from typing import Optional

from app.auth_utils import hash_password
from app.database import get_session
from app.deps import require_role
from app.email_validator import validate_email_format
from app.models import User
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/users")
def list_users(
    request: Request,
    sort: Optional[str] = Query("created"),
    direction: Optional[str] = Query("desc"),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["admin"])),
):
    """List users with optional sorting by column."""
    users = session.exec(select(User)).all()

    key_map = {
        "name": lambda u: u.name or "",
        "email": lambda u: u.email or "",
        "role": lambda u: u.role or "",
        "active": lambda u: (1 if u.is_active else 0, u.name or ""),
        "created": lambda u: u.created_at,
    }

    sort_key = key_map.get(sort or "created", key_map["created"])
    is_desc = (direction or "desc").lower() == "desc"

    users_sorted = sorted(users, key=sort_key, reverse=is_desc)

    context = {
        "request": request,
        "users": users_sorted,
        "sort": sort,
        "direction": "desc" if is_desc else "asc",
        "has_sort": (sort not in (None, "", "created") or (direction or "desc").lower() != "desc"),
        "current_user": current_user,
    }
    return templates.TemplateResponse("admin/user_list.html", context)


@router.get("/users/{user_id}/edit")
def edit_user_form(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["admin"])),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    form = {
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "title": getattr(user, "title", None) or "",
        "staff_id": getattr(user, "staff_id", None) or "",
        "phone": getattr(user, "phone", None) or "",
        "status": getattr(user, "status", "active") or "active",
    }
    context = {
        "request": request,
        "user_id": user_id,
        "form": form,
        "errors": {},
        "current_user": current_user,
    }
    return templates.TemplateResponse("admin/user_form.html", context)


@router.post("/users/{user_id}/edit")
def edit_user(
    user_id: int,
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    is_active: Optional[bool] = Form(False),
    title: str = Form(None),
    staff_id: str = Form(None),
    phone: str = Form(None),
    status_field: str = Form("active"),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["admin"])),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    errors: dict[str, str] = {}
    name_clean = name.strip()
    email_clean = email.strip().lower()
    role_clean = role.strip()
    title_clean = title.strip() if title else None
    staff_id_clean = staff_id.strip() if staff_id else None
    phone_clean = phone.strip() if phone else None

    if not name_clean:
        errors["name"] = "Name is required."
    
    # Email validation with TLD checking
    if not email_clean:
        errors["email"] = "Email is required."
    else:
        email_error = validate_email_format(email_clean)
        if email_error:
            errors["email"] = email_error
    
    if role_clean not in ("admin", "lecturer", "student"):
        errors["role"] = "Role must be admin, lecturer, or student."

    # Validate title if provided
    if title_clean and title_clean not in [
        "",
        "Dr.",
        "Prof.",
        "Assoc. Prof.",
        "Mr.",
        "Ms.",
        "Mrs.",
        "Ir.",
        "Ts.",
    ]:
        errors["title"] = "Please select a valid title."

    # Validate phone if provided
    if phone_clean:
        phone_digits = "".join(filter(str.isdigit, phone_clean))
        if len(phone_digits) < 7 or len(phone_digits) > 15:
            errors["phone"] = "Please enter a valid phone number (7-15 digits)."

    # Check for duplicate email on other users
    existing = session.exec(select(User).where(User.email == email_clean, User.id != user_id)).first()
    if existing:
        errors["email"] = "Another user already uses this email."

    # Check for duplicate staff_id on other users (if provided and role is lecturer)
    if staff_id_clean and role_clean == "lecturer":
        existing_staff = session.exec(select(User).where(User.staff_id == staff_id_clean, User.id != user_id)).first()
        if existing_staff:
            errors["staff_id"] = "This Staff ID is already in use by another user."

    if errors:
        form = {
            "name": name,
            "email": email,
            "role": role,
            "is_active": is_active,
            "title": title,
            "staff_id": staff_id,
            "phone": phone,
            "status": status_field,
        }
        context = {
            "request": request,
            "user_id": user_id,
            "form": form,
            "errors": errors,
            "current_user": current_user,
        }
        return templates.TemplateResponse("admin/user_form.html", context, status_code=status.HTTP_400_BAD_REQUEST)

    user.name = name_clean
    user.email = email_clean
    user.role = role_clean
    user.is_active = bool(is_active)

    # Update lecturer-specific fields
    if hasattr(user, "title"):
        user.title = title_clean
    if hasattr(user, "staff_id"):
        user.staff_id = staff_id_clean if role_clean == "lecturer" else None
    if hasattr(user, "phone"):
        user.phone = phone_clean
    if hasattr(user, "status"):
        user.status = status_field if status_field in ["active", "suspended"] else "active"

    session.add(user)
    session.commit()

    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/users/new-lecturer")
def new_lecturer_form(
    request: Request,
    current_user: User = Depends(require_role(["admin"])),
):
    """Form to create a new lecturer account."""
    context = {
        "request": request,
        "form": None,
        "errors": {},
        "current_user": current_user,
    }
    return templates.TemplateResponse("admin/lecturer_form.html", context)


@router.post("/users/new-lecturer")
def create_lecturer(
    request: Request,
    title: str = Form(None),
    name: str = Form(...),
    staff_id: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    password: str = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["admin"])),
):
    """Create a new lecturer account."""
    errors: dict[str, str] = {}
    title_clean = title.strip() if title else None
    name_clean = name.strip()
    staff_id_clean = staff_id.strip() if staff_id else None
    email_clean = email.strip().lower()
    phone_clean = phone.strip() if phone else None

    # Validation
    if title_clean and title_clean not in [
        "Dr.",
        "Prof.",
        "Assoc. Prof.",
        "Mr.",
        "Ms.",
        "Mrs.",
        "Ir.",
        "Ts.",
    ]:
        errors["title"] = "Please select a valid title."

    if not name_clean:
        errors["name"] = "Full name is required."
    elif len(name_clean) < 2:
        errors["name"] = "Name must be at least 2 characters long."

    if not staff_id_clean:
        errors["staff_id"] = "Staff ID is required."
    elif len(staff_id_clean) < 3:
        errors["staff_id"] = "Staff ID must be at least 3 characters long."

    # Email validation with TLD checking
    if not email_clean:
        errors["email"] = "Email is required."
    else:
        email_error = validate_email_format(email_clean)
        if email_error:
            errors["email"] = email_error

    if phone_clean:
        phone_digits = "".join(filter(str.isdigit, phone_clean))
        if len(phone_digits) < 7 or len(phone_digits) > 15:
            errors["phone"] = "Please enter a valid phone number (7-15 digits)."

    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 8:
        errors["password"] = "Password must be at least 8 characters long."

    # Check for duplicate email
    existing_email = session.exec(select(User).where(User.email == email_clean)).first()
    if existing_email:
        errors["email"] = "This email is already registered."

    # Check for duplicate staff_id
    if staff_id_clean:
        existing_staff = session.exec(select(User).where(User.staff_id == staff_id_clean)).first()
        if existing_staff:
            errors["staff_id"] = "This Staff ID is already in use."

    if errors:
        context = {
            "request": request,
            "form": {
                "title": title,
                "name": name,
                "staff_id": staff_id,
                "email": email,
                "phone": phone,
            },
            "errors": errors,
            "current_user": current_user,
        }
        return templates.TemplateResponse("admin/lecturer_form.html", context, status_code=status.HTTP_400_BAD_REQUEST)

    # Create lecturer user
    lecturer = User(
        title=title_clean,
        name=name_clean,
        staff_id=staff_id_clean,
        email=email_clean,
        phone=phone_clean,
        password_hash=hash_password(password),
        role="lecturer",
        is_active=True,
        status="active",
    )
    session.add(lecturer)
    session.commit()

    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/reactivate-admin")
def reactivate_admin(
    session: Session = Depends(get_session),
):
    """Emergency route to reactivate the admin account if accidentally suspended.
    This route can be accessed without authentication for emergency recovery."""
    admin = session.exec(select(User).where(User.email == "admin@example.com")).first()
    if admin:
        admin.is_active = True
        if hasattr(admin, "status"):
            admin.status = "active"
        session.add(admin)
        session.commit()
        return {"message": "Admin account reactivated successfully. You can now log in."}
    return {"message": "Admin account not found."}


@router.get("/performance-report")
def performance_summary_report(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["admin"])),
):
    """Generate student performance summary report by subject.

    Shows:
    - Average score per subject
    - Pass rate per subject
    - Number of students who took the exam
    - Highest/lowest scores
    """
    from app.models import Exam, ExamAttempt, EssayAnswer, ExamQuestion, MCQResult
    from datetime import datetime

    try:
        # Dictionary to store subject-wise performance data
        subject_data: dict = {}

        # Collect MCQ results
        mcq_results = session.exec(select(MCQResult)).all()

        for mcq_result in mcq_results:
            exam = session.get(Exam, mcq_result.exam_id)
            if not exam or not exam.subject:
                continue

            subject = exam.subject
            percentage = (mcq_result.score / mcq_result.total_questions * 100) if mcq_result.total_questions > 0 else 0
            is_passed = percentage >= 60  # Pass threshold: 60%

            if subject not in subject_data:
                subject_data[subject] = {
                    "subject": subject,
                    "total_students": 0,
                    "total_score": 0,
                    "passed_count": 0,
                    "scores": [],
                    "exam_types": set(),
                }

            subject_data[subject]["total_students"] += 1
            subject_data[subject]["total_score"] += percentage
            subject_data[subject]["scores"].append(percentage)
            subject_data[subject]["exam_types"].add("MCQ")

            if is_passed:
                subject_data[subject]["passed_count"] += 1

        # Collect Essay results
        essay_attempts = session.exec(
            select(ExamAttempt).where(ExamAttempt.status.in_(["submitted", "timed_out"]))
        ).all()

        for attempt in essay_attempts:
            exam = session.get(Exam, attempt.exam_id)
            if not exam or not exam.subject:
                continue

            # Check if graded
            answers = session.exec(select(EssayAnswer).where(EssayAnswer.attempt_id == attempt.id)).all()

            is_graded = any(a.marks_awarded is not None for a in answers)
            if not is_graded:
                continue  # Skip ungraded essays

            total_marks = sum((a.marks_awarded or 0) for a in answers)

            # Get total possible marks
            questions = session.exec(select(ExamQuestion).where(ExamQuestion.exam_id == attempt.exam_id)).all()
            total_possible = sum((q.max_marks or 0) for q in questions)

            percentage = (total_marks / total_possible * 100) if total_possible > 0 else 0
            is_passed = percentage >= 60

            subject = exam.subject

            if subject not in subject_data:
                subject_data[subject] = {
                    "subject": subject,
                    "total_students": 0,
                    "total_score": 0,
                    "passed_count": 0,
                    "scores": [],
                    "exam_types": set(),
                }

            subject_data[subject]["total_students"] += 1
            subject_data[subject]["total_score"] += percentage
            subject_data[subject]["scores"].append(percentage)
            subject_data[subject]["exam_types"].add("Essay")

            if is_passed:
                subject_data[subject]["passed_count"] += 1

        # Calculate averages and pass rates
        report_data = []

        for subject, data in sorted(subject_data.items()):
            if data["total_students"] == 0:
                continue

            avg_score = data["total_score"] / data["total_students"]
            pass_rate = data["passed_count"] / data["total_students"] * 100
            highest_score = max(data["scores"]) if data["scores"] else 0
            lowest_score = min(data["scores"]) if data["scores"] else 0

            report_data.append(
                {
                    "subject": subject,
                    "average_score": f"{avg_score:.2f}",
                    "pass_rate": f"{pass_rate:.1f}",
                    "total_students": data["total_students"],
                    "passed_count": data["passed_count"],
                    "highest_score": f"{highest_score:.2f}",
                    "lowest_score": f"{lowest_score:.2f}",
                    "exam_types": ", ".join(sorted(data["exam_types"])),
                }
            )

        context = {
            "request": request,
            "report_data": report_data,
            "total_subjects": len(report_data),
            "current_user": current_user,
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return templates.TemplateResponse("admin/performance_report.html", context)

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")
