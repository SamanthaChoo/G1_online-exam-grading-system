"""Authentication and account management routes."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.auth_utils import create_reset_token, hash_password, verify_password
from app.database import get_session
from app.deps import get_current_user
from app.models import PasswordResetToken, Student, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
def login_form(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    if current_user:
        # Already logged in – send to a sensible default depending on role
        if current_user.role in ("lecturer", "admin"):
            return RedirectResponse(url="/courses/", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/courses/", status_code=status.HTTP_303_SEE_OTHER)

    context = {"request": request, "form": None, "error": None}
    return templates.TemplateResponse("auth/login.html", context)


@router.post("/login")
def login(
    request: Request,
    login_type: str = Form("admin"),
    email: Optional[str] = Form(None),
    staff_id: Optional[str] = Form(None),
    matric_no: Optional[str] = Form(None),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = None
    error = None
    form_data = {"login_type": login_type}

    # Find user based on login type
    if login_type == "admin":
        if not email:
            error = "Email is required for admin login."
        else:
            email_clean = email.strip().lower()
            form_data["email"] = email
            user = session.exec(select(User).where(User.email == email_clean)).first()
            if user and user.role != "admin":
                error = "This email is not registered as an admin account."
                user = None
            elif not user:
                error = "Invalid email or password."
    
    elif login_type == "lecturer":
        if not staff_id:
            error = "Staff ID is required for lecturer login."
        else:
            staff_id_clean = staff_id.strip()
            form_data["staff_id"] = staff_id
            # Find lecturer by staff_id
            user = session.exec(
                select(User).where(
                    User.staff_id == staff_id_clean,
                    User.role == "lecturer"
                )
            ).first()
            if not user:
                error = "Invalid Staff ID or password. Please check your Staff ID and try again."
            elif user and user.role != "lecturer":
                error = "This Staff ID is not registered as a lecturer account."
                user = None
    
    elif login_type == "student":
        if not matric_no:
            error = "Student ID / Matric Number is required for student login."
        else:
            matric_clean = matric_no.strip()
            form_data["matric_no"] = matric_no
            # Find student by matric number
            student = session.exec(
                select(Student).where(Student.matric_no == matric_clean)
            ).first()
            if student and student.user_id:
                # Get the linked user account
                user = session.get(User, student.user_id)
                if user and user.role != "student":
                    error = "Invalid Student ID or password."
                    user = None
            if not user:
                error = "Invalid Student ID or password."

    # Validate password and account status
    if user:
        if not verify_password(password, user.password_hash):
            error = "Invalid credentials. Please check your login details and try again."
            user = None
        elif not user.is_active:
            error = "Your account is inactive. Please contact an administrator."
            user = None
        elif hasattr(user, 'status') and user.status == "suspended":
            error = "Your account has been suspended. Please contact an administrator."
            user = None

    if error or not user:
        context = {
            "request": request,
            "form": form_data,
            "error": error or "Invalid login credentials. Please try again.",
        }
        return templates.TemplateResponse(
            "auth/login.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    # Update last_login timestamp
    from datetime import datetime
    user.last_login = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)  # Refresh to ensure we have the latest data

    # Clear any existing session first to avoid conflicts
    request.session.clear()
    
    # Successful login: remember user in session
    # Set session before redirect to ensure it's saved
    request.session["user_id"] = user.id
    
    # Verify the user role one more time before redirecting
    # This ensures we're redirecting the correct user
    if user.role == "admin":
        redirect_url = "/admin/users"
    elif user.role == "lecturer":
        redirect_url = "/courses/"
    else:  # student
        redirect_url = "/"  # Home page for students

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    
    # Ensure session is saved by setting it in the response
    # The session middleware will handle saving the session cookie
    return response


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/register-student")
def register_student_form(request: Request):
    context = {"request": request, "form": None, "errors": {}}
    return templates.TemplateResponse("auth/register_student.html", context)


@router.post("/register-student")
def register_student(
    request: Request,
    name: str = Form(...),
    matric_no: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    program: str = Form(None),
    year_of_study: str = Form(None),
    phone_number: str = Form(None),
    session: Session = Depends(get_session),
):
    errors: dict[str, str] = {}

    name_clean = name.strip()
    matric_clean = matric_no.strip()
    email_clean = email.strip().lower()
    program_clean = program.strip() if program else None
    year_of_study_int = None
    phone_clean = phone_number.strip() if phone_number else None

    # Name validation
    if not name_clean:
        errors["name"] = "Full name is required."
    elif len(name_clean) < 2:
        errors["name"] = "Name must be at least 2 characters long."
    elif len(name_clean) > 100:
        errors["name"] = "Name must not exceed 100 characters."

    # Matric/Student ID validation
    if not matric_clean:
        errors["matric_no"] = "Matric / Student ID is required."
    elif len(matric_clean) < 3:
        errors["matric_no"] = "Student ID must be at least 3 characters long."
    elif len(matric_clean) > 50:
        errors["matric_no"] = "Student ID must not exceed 50 characters."
    
    # Check for duplicate matric_no
    if "matric_no" not in errors:
        existing_student_matric = session.exec(
            select(Student).where(Student.matric_no == matric_clean)
        ).first()
        if existing_student_matric:
            errors["matric_no"] = "This Student ID is already registered. Please use a different ID or contact support."

    # Email validation
    if not email_clean:
        errors["email"] = "Email address is required."
    elif "@" not in email_clean or "." not in email_clean.split("@")[-1]:
        errors["email"] = "Please enter a valid email address."
    elif len(email_clean) > 255:
        errors["email"] = "Email address is too long."

    # Check for existing email in both User and Student tables (only if email format is valid)
    if "email" not in errors:
        existing_user = session.exec(select(User).where(User.email == email_clean)).first()
        if existing_user:
            errors["email"] = "This email is already registered. Please use a different email or try logging in."
        else:
            existing_student_email = session.exec(
                select(Student).where(Student.email == email_clean)
            ).first()
            if existing_student_email:
                errors["email"] = "This email is already registered. Please use a different email or try logging in."

    # Optional: Program validation
    if program_clean:
        if len(program_clean) > 50:
            errors["program"] = "Program name must not exceed 50 characters."

    # Optional: Year of Study validation
    if year_of_study:
        try:
            year_of_study_int = int(year_of_study)
            if year_of_study_int < 1 or year_of_study_int > 10:
                errors["year_of_study"] = "Year of study must be between 1 and 10."
        except ValueError:
            errors["year_of_study"] = "Please select a valid year of study."

    # Optional: Phone number validation
    if phone_clean:
        # Remove common phone number characters for validation
        phone_digits = ''.join(filter(str.isdigit, phone_clean))
        if len(phone_digits) < 7 or len(phone_digits) > 15:
            errors["phone_number"] = "Please enter a valid phone number (7-15 digits)."
        elif len(phone_clean) > 20:
            errors["phone_number"] = "Phone number must not exceed 20 characters."

    # Password validation
    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 8:
        errors["password"] = "Password must be at least 8 characters long."
    elif len(password) > 128:
        errors["password"] = "Password must not exceed 128 characters."
    elif not any(c.isupper() for c in password):
        errors["password"] = "Password must contain at least one uppercase letter."
    elif not any(c.islower() for c in password):
        errors["password"] = "Password must contain at least one lowercase letter."
    elif not any(c.isdigit() for c in password):
        errors["password"] = "Password must contain at least one number."
    elif not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for c in password):
        errors["password"] = "Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?/~`)."

    # Confirm password validation
    if not confirm_password:
        errors["confirm_password"] = "Please confirm your password."
    elif password != confirm_password:
        errors["confirm_password"] = "Passwords do not match. Please try again."

    if errors:
        context = {
            "request": request,
            "form": {
                "name": name,
                "matric_no": matric_no,
                "email": email,
                "program": program,
                "year_of_study": year_of_study,
                "phone_number": phone_number,
            },
            "errors": errors,
        }
        return templates.TemplateResponse(
            "auth/register_student.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )

    # Create Student record
    student = Student(
        name=name_clean,
        email=email_clean,
        matric_no=matric_clean,
        program=program_clean,
        year_of_study=year_of_study_int,
        phone_number=phone_clean,
    )
    session.add(student)
    session.commit()
    session.refresh(student)

    # Create User linked to Student
    user = User(
        name=name_clean,
        email=email_clean,
        password_hash=hash_password(password),
        role="student",
        student_id=student.id,
    )
    session.add(user)
    session.commit()

    # Link back from Student to User
    student.user_id = user.id
    session.add(student)
    session.commit()

    # Auto-login newly registered student
    request.session["user_id"] = user.id

    return RedirectResponse(url="/courses/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/request-reset")
def request_reset_form(request: Request):
    context = {"request": request, "submitted": False}
    return templates.TemplateResponse("auth/request_reset.html", context)


@router.post("/request-reset")
def request_reset(
    request: Request,
    email: str = Form(...),
    session: Session = Depends(get_session),
):
    email_clean = email.strip().lower()
    user = session.exec(select(User).where(User.email == email_clean)).first()

    reset_link: Optional[str] = None

    if user:
        token = create_reset_token()
        expires_at = datetime.utcnow() + timedelta(minutes=30)
        reset_token = PasswordResetToken(
            user_id=user.id, token=token, expires_at=expires_at
        )
        session.add(reset_token)
        session.commit()

        reset_link = f"http://127.0.0.1:8000/auth/reset-password?token={token}"
        # For this assignment we "simulate" email by printing to console
        print(f"[Password reset] Send this link to the user: {reset_link}")

    context = {
        "request": request,
        "submitted": True,
        "reset_link": reset_link,  # visible only in dev template
    }
    return templates.TemplateResponse("auth/request_reset.html", context)


def _load_valid_token(token: str, session: Session) -> PasswordResetToken:
    reset_token = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token == token)
    ).first()
    if (
        not reset_token
        or reset_token.used
        or reset_token.expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    return reset_token


@router.get("/reset-password")
def reset_password_form(
    request: Request,
    token: str,
    session: Session = Depends(get_session),
):
    # Validate token before showing the form
    try:
        _load_valid_token(token, session)
    except HTTPException as exc:
        if exc.status_code == 400:
            context = {"request": request, "error": exc.detail}
            return templates.TemplateResponse(
                "auth/reset_password_invalid.html",
                context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        raise

    context = {"request": request, "token": token, "errors": {}}
    return templates.TemplateResponse("auth/reset_password.html", context)


@router.post("/reset-password")
def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    session: Session = Depends(get_session),
):
    errors: dict[str, str] = {}
    if not password:
        errors["password"] = "Password is required."
    if password != confirm_password:
        errors["confirm_password"] = "Passwords do not match."

    if errors:
        context = {"request": request, "token": token, "errors": errors}
        return templates.TemplateResponse(
            "auth/reset_password.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        reset_token = _load_valid_token(token, session)
    except HTTPException as exc:
        if exc.status_code == 400:
            context = {"request": request, "error": exc.detail}
            return templates.TemplateResponse(
                "auth/reset_password_invalid.html",
                context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        raise

    user = session.get(User, reset_token.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User not found for token.")

    user.password_hash = hash_password(password)
    reset_token.used = True
    session.add(user)
    session.add(reset_token)
    session.commit()

    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)


