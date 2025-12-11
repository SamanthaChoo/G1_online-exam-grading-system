"""Authentication and account management routes."""

from datetime import datetime, timedelta
from typing import Optional

from app.auth_utils import create_reset_token, generate_otp, hash_password, verify_password
from app.database import get_session
from app.deps import get_current_user
from app.email_utils import send_otp_email
from app.email_validator import validate_email_format
from app.models import PasswordResetOTP, PasswordResetToken, Student, User
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlmodel import Session, select

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
def login_form(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    if current_user:
        # Already logged in – send to a sensible default depending on role
        if current_user.role == "admin":
            return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)
        elif current_user.role == "lecturer":
            return RedirectResponse(url="/courses/", status_code=status.HTTP_303_SEE_OTHER)
        else:  # student
            return RedirectResponse(url="/courses/student", status_code=status.HTTP_303_SEE_OTHER)

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
            user = session.exec(select(User).where(User.staff_id == staff_id_clean, User.role == "lecturer")).first()
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
            student = session.exec(select(Student).where(Student.matric_no == matric_clean)).first()
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
        elif hasattr(user, "status") and user.status == "suspended":
            error = "Your account has been suspended. Please contact an administrator."
            user = None

    if error or not user:
        context = {
            "request": request,
            "form": form_data,
            "error": error or "Invalid login credentials. Please try again.",
        }
        return templates.TemplateResponse("auth/login.html", context, status_code=status.HTTP_400_BAD_REQUEST)

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
        redirect_url = "/courses/student"  # Student course list page

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    # Ensure session is saved by setting it in the response
    # The session middleware will handle saving the session cookie
    return response


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/check-student-id")
def check_student_id(
    matric_no: str,
    session: Session = Depends(get_session),
):
    """API endpoint to check if a student ID already exists (for live validation)."""
    matric_clean = matric_no.strip()
    
    if not matric_clean or len(matric_clean) < 3:
        return {"available": True, "message": ""}
    
    # Check for exact match
    existing_student = session.exec(select(Student).where(Student.matric_no == matric_clean)).first()
    
    if existing_student:
        if existing_student.user_id:
            return {
                "available": False,
                "message": "This Student ID is already registered with an account. Please use a different ID or try logging in.",
            }
        else:
            return {
                "available": False,
                "message": "This Student ID is already registered. Please use a different ID or contact support.",
            }
    
    # Also check case-insensitively
    existing_case = session.exec(
        select(Student).where(func.lower(Student.matric_no) == matric_clean.lower())
    ).first()
    
    if existing_case and existing_case.matric_no != matric_clean:
        return {
            "available": False,
            "message": "A similar Student ID already exists. Please check your Student ID and try again.",
        }
    
    return {"available": True, "message": ""}


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

    # Check for duplicate matric_no (case-insensitive and check if already has a user account)
    if "matric_no" not in errors:
        # Check for exact match (case-sensitive first, as matric numbers are usually case-sensitive)
        existing_student_exact = session.exec(select(Student).where(Student.matric_no == matric_clean)).first()
        if existing_student_exact:
            # Check if this student already has a user account
            if existing_student_exact.user_id:
                errors["matric_no"] = "This Student ID is already registered with an account. Please use a different ID or try logging in."
            else:
                errors["matric_no"] = "This Student ID is already registered. Please use a different ID or contact support."
        
        # Also check case-insensitively to catch variations (only if exact match didn't find anything)
        if "matric_no" not in errors:
            existing_student_case = session.exec(
                select(Student).where(func.lower(Student.matric_no) == matric_clean.lower())
            ).first()
            if existing_student_case and existing_student_case.matric_no != matric_clean:
                errors["matric_no"] = "A similar Student ID already exists. Please check your Student ID and try again."

    # Email validation with TLD checking
    email_error = validate_email_format(email_clean)
    if email_error:
        errors["email"] = email_error

    # Check for existing email in both User and Student tables (only if email format is valid)
    if "email" not in errors:
        existing_user = session.exec(select(User).where(User.email == email_clean)).first()
        if existing_user:
            errors["email"] = "This email is already registered. Please use a different email or try logging in."
        else:
            existing_student_email = session.exec(select(Student).where(Student.email == email_clean)).first()
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
        phone_digits = "".join(filter(str.isdigit, phone_clean))
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
            "auth/register_student.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Create Student record
    # Double-check uniqueness before creating (in case of race condition)
    final_check = session.exec(select(Student).where(Student.matric_no == matric_clean)).first()
    if final_check:
        errors["matric_no"] = "This Student ID is already registered. Please use a different ID or contact support."
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
            "auth/register_student.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    
    student = Student(
        name=name_clean,
        email=email_clean,
        matric_no=matric_clean,
        program=program_clean,
        year_of_study=year_of_study_int,
        phone_number=phone_clean,
    )
    session.add(student)
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        # Check if it's a unique constraint violation
        if "uq_student_matric_no" in str(e) or "UNIQUE constraint" in str(e) or "unique" in str(e).lower():
            errors["matric_no"] = "This Student ID is already registered. Please use a different ID or contact support."
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
                "auth/register_student.html",
                context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        raise  # Re-raise if it's a different error
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

    return RedirectResponse(url="/courses/student", status_code=status.HTTP_303_SEE_OTHER)


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
    
    # Validate email format first (including TLD check)
    email_error = validate_email_format(email_clean)
    if email_error:
        context = {
            "request": request,
            "submitted": False,
            "error": email_error,
            "email": email,
        }
        return templates.TemplateResponse(
            "auth/request_reset.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    
    user = session.exec(select(User).where(User.email == email_clean)).first()

    # Check if email exists
    if not user:
        context = {
            "request": request,
            "submitted": False,
            "error": "Account not found. Please check your email address and try again.",
            "email": email,
        }
        return templates.TemplateResponse(
            "auth/request_reset.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Generate 6-digit OTP
    otp_code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    # Invalidate any existing unused OTPs for this user
    existing_otps = session.exec(
        select(PasswordResetOTP).where(
            PasswordResetOTP.user_id == user.id,
            PasswordResetOTP.used == False,
            PasswordResetOTP.expires_at > datetime.utcnow(),
        )
    ).all()
    for otp in existing_otps:
        otp.used = True
        session.add(otp)

    # Create new OTP
    reset_otp = PasswordResetOTP(
        user_id=user.id,
        otp_code=otp_code,
        expires_at=expires_at,
    )
    session.add(reset_otp)
    session.commit()

    # Send OTP via email
    email_sent = send_otp_email(user.email, otp_code, user.name)
    if not email_sent:
        context = {
            "request": request,
            "submitted": False,
            "error": "Failed to send email. Please try again later.",
            "email": email,
        }
        return templates.TemplateResponse(
            "auth/request_reset.html",
            context,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Store user_id in session for OTP verification
    request.session["reset_user_id"] = user.id
    request.session["reset_email"] = user.email

    context = {
        "request": request,
        "submitted": True,
        "email": user.email,
    }
    return templates.TemplateResponse("auth/verify_otp.html", context)


def _load_valid_token(token: str, session: Session) -> PasswordResetToken:
    reset_token = session.exec(select(PasswordResetToken).where(PasswordResetToken.token == token)).first()
    if not reset_token or reset_token.used or reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    return reset_token


def _load_valid_otp(otp_code: str, user_id: int, session: Session) -> PasswordResetOTP:
    """Load and validate OTP code."""
    reset_otp = session.exec(
        select(PasswordResetOTP).where(
            PasswordResetOTP.otp_code == otp_code,
            PasswordResetOTP.user_id == user_id,
            PasswordResetOTP.used == False,
        )
    ).first()
    if not reset_otp:
        raise HTTPException(status_code=400, detail="Invalid OTP code.")
    if reset_otp.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP code has expired. Please request a new one.")
    return reset_otp


@router.get("/verify-otp")
def verify_otp_form(request: Request):
    """Show OTP verification form."""
    user_id = request.session.get("reset_user_id")
    if not user_id:
        return RedirectResponse(url="/auth/request-reset", status_code=status.HTTP_303_SEE_OTHER)

    context = {
        "request": request,
        "email": request.session.get("reset_email", ""),
        "error": None,
    }
    return templates.TemplateResponse("auth/verify_otp.html", context)


@router.post("/verify-otp")
def verify_otp(
    request: Request,
    otp_code: str = Form(...),
    session: Session = Depends(get_session),
):
    """Verify OTP code and redirect to password reset form."""
    user_id = request.session.get("reset_user_id")
    if not user_id:
        return RedirectResponse(url="/auth/request-reset", status_code=status.HTTP_303_SEE_OTHER)

    otp_clean = otp_code.strip()

    # Validate OTP format (6 digits)
    if not otp_clean.isdigit() or len(otp_clean) != 6:
        context = {
            "request": request,
            "email": request.session.get("reset_email", ""),
            "error": "Invalid OTP format. Please enter a 6-digit code.",
        }
        return templates.TemplateResponse(
            "auth/verify_otp.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        reset_otp = _load_valid_otp(otp_clean, user_id, session)
        # Mark OTP as used
        reset_otp.used = True
        session.add(reset_otp)
        session.commit()

        # Store verification in session
        request.session["otp_verified"] = True
        request.session["reset_user_id"] = user_id

        return RedirectResponse(url="/auth/reset-password", status_code=status.HTTP_303_SEE_OTHER)
    except HTTPException as exc:
        context = {
            "request": request,
            "email": request.session.get("reset_email", ""),
            "error": exc.detail,
        }
        return templates.TemplateResponse(
            "auth/verify_otp.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.post("/resend-otp")
def resend_otp(
    request: Request,
    session: Session = Depends(get_session),
):
    """Resend OTP code."""
    user_id = request.session.get("reset_user_id")
    if not user_id:
        return RedirectResponse(url="/auth/request-reset", status_code=status.HTTP_303_SEE_OTHER)

    user = session.get(User, user_id)
    if not user:
        return RedirectResponse(url="/auth/request-reset", status_code=status.HTTP_303_SEE_OTHER)

    # Generate new OTP
    otp_code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    # Invalidate any existing unused OTPs for this user
    existing_otps = session.exec(
        select(PasswordResetOTP).where(
            PasswordResetOTP.user_id == user.id,
            PasswordResetOTP.used == False,
            PasswordResetOTP.expires_at > datetime.utcnow(),
        )
    ).all()
    for otp in existing_otps:
        otp.used = True
        session.add(otp)

    # Create new OTP
    reset_otp = PasswordResetOTP(
        user_id=user.id,
        otp_code=otp_code,
        expires_at=expires_at,
    )
    session.add(reset_otp)
    session.commit()

    # Send OTP via email
    email_sent = send_otp_email(user.email, otp_code, user.name)
    if not email_sent:
        context = {
            "request": request,
            "email": user.email,
            "error": "Failed to send email. Please try again later.",
        }
        return templates.TemplateResponse(
            "auth/verify_otp.html",
            context,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    context = {
        "request": request,
        "email": user.email,
        "success": "A new OTP code has been sent to your email.",
    }
    return templates.TemplateResponse("auth/verify_otp.html", context)


@router.get("/reset-password")
def reset_password_form(
    request: Request,
    session: Session = Depends(get_session),
):
    """Show password reset form after OTP verification."""
    user_id = request.session.get("reset_user_id")
    otp_verified = request.session.get("otp_verified")

    if not user_id or not otp_verified:
        return RedirectResponse(url="/auth/request-reset", status_code=status.HTTP_303_SEE_OTHER)

    context = {"request": request, "errors": {}}
    return templates.TemplateResponse("auth/reset_password.html", context)


@router.post("/reset-password")
def reset_password(
    request: Request,
    password: str = Form(...),
    confirm_password: str = Form(...),
    session: Session = Depends(get_session),
):
    """Reset password after OTP verification."""
    user_id = request.session.get("reset_user_id")
    otp_verified = request.session.get("otp_verified")

    if not user_id or not otp_verified:
        return RedirectResponse(url="/auth/request-reset", status_code=status.HTTP_303_SEE_OTHER)

    errors: dict[str, str] = {}

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
        errors["confirm_password"] = "Passwords do not match."

    if errors:
        context = {"request": request, "errors": errors}
        return templates.TemplateResponse(
            "auth/reset_password.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")

    # Update password
    user.password_hash = hash_password(password)
    session.add(user)
    session.commit()

    # Clear reset session
    request.session.pop("reset_user_id", None)
    request.session.pop("otp_verified", None)
    request.session.pop("reset_email", None)

    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
