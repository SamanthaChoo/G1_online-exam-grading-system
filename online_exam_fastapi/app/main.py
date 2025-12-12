"""FastAPI entrypoint for the Online Examination & Grading System."""

from app.auth_utils import hash_password
from app.database import create_db_and_tables, engine
from app.deps import get_current_user
from app.models import Student, User
from app.routers import admin as admin_router_module
from app.routers import auth as auth_router_module
from app.routers import courses as courses_router_module
from app.routers import essay as essay_router_module
from app.routers import essay_ui as essay_ui_router
from app.routers import exams as exams_router_module
from app.routers import lecturer as lecturer_router_module
from app.routers import mcq as mcq_router_module
from app.routers import student as student_router_module
from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(title="Online Examination & Grading System")

# Templates must be defined before exception handlers that use them
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle form validation errors and return HTML responses for HTML requests."""
    accept_header = request.headers.get("accept", "")

    # If it's an HTML request, return the appropriate form with errors
    if "text/html" in accept_header or request.method == "POST":
        # Extract field names from validation errors and convert to user-friendly messages
        errors_dict = {}
        field_name_mapping = {
            "name": "Full name",
            "matric_no": "Matric / Student ID",
            "email": "Email address",
            "password": "Password",
            "confirm_password": "Confirm password",
        }

        for error in exc.errors():
            field_path = error.get("loc", [])
            if field_path:
                # Get the last element (field name) from the path
                field_name = (
                    field_path[-1]
                    if isinstance(field_path[-1], str)
                    else str(field_path[-1])
                )
                error_type = error.get("type", "")
                error_msg = error.get("msg", "Invalid input")

                # Convert technical error messages to user-friendly ones
                if error_type == "missing":
                    display_name = field_name_mapping.get(
                        field_name, field_name.replace("_", " ").title()
                    )
                    errors_dict[field_name] = f"{display_name} is required."
                else:
                    # Use the field name mapping for better display
                    display_name = field_name_mapping.get(
                        field_name, field_name.replace("_", " ").title()
                    )
                    errors_dict[field_name] = f"{display_name}: {error_msg}"

        # Determine which form to show based on the URL
        url_path = request.url.path

        if "/register-student" in url_path:
            context = {
                "request": request,
                "form": {
                    "name": "",
                    "matric_no": "",
                    "email": "",
                    "program": "",
                    "year_of_study": "",
                    "phone_number": "",
                },
                "errors": errors_dict,
            }
            return templates.TemplateResponse(
                "auth/register_student.html",
                context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        elif "/request-reset" in url_path:
            context = {
                "request": request,
                "submitted": False,
                "error": "Please fill in all required fields.",
                "email": "",
            }
            return templates.TemplateResponse(
                "auth/request_reset.html",
                context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        elif "/verify-otp" in url_path:
            context = {
                "request": request,
                "email": request.session.get("reset_email", ""),
                "error": "Please enter a valid 6-digit OTP code.",
            }
            return templates.TemplateResponse(
                "auth/verify_otp.html",
                context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        elif "/reset-password" in url_path:
            context = {
                "request": request,
                "errors": errors_dict,
            }
            return templates.TemplateResponse(
                "auth/reset_password.html",
                context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    # For API requests, return JSON
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions, especially 403 Forbidden for HTML requests."""
    # If it's a 403 and the request is for HTML, redirect to home
    if exc.status_code == 403:
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header or request.method == "GET":
            return RedirectResponse(
                url="/?error=access_denied", status_code=status.HTTP_303_SEE_OTHER
            )
    # For 303 redirects (like login redirects), let them pass through
    if exc.status_code == 303 and exc.headers.get("Location"):
        return RedirectResponse(
            url=exc.headers["Location"], status_code=status.HTTP_303_SEE_OTHER
        )
    # For other cases or API requests, use default behavior
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# Session middleware for simple cookie-based authentication
app.add_middleware(SessionMiddleware, secret_key="CHANGE_ME_TO_A_RANDOM_SECRET")

# Static + templates configuration
app.mount("/static", StaticFiles(directory="app/static"), name="static")
# templates already defined above for exception handlers

# Routers
app.include_router(auth_router_module.router, prefix="/auth", tags=["auth"])
app.include_router(admin_router_module.router, prefix="/admin", tags=["admin"])
app.include_router(lecturer_router_module.router, prefix="/lecturer", tags=["lecturer"])
app.include_router(courses_router_module.router, prefix="/courses", tags=["courses"])
app.include_router(exams_router_module.router, prefix="/exams", tags=["exams"])
app.include_router(mcq_router_module.router, prefix="/exams", tags=["mcq"])
app.include_router(essay_router_module.router)
app.include_router(essay_ui_router.router)
app.include_router(student_router_module.router, tags=["student"])


@app.get("/")
def home(
    request: Request,
    current_user: User | None = Depends(get_current_user),
    error: str | None = Query(None),
):
    """Landing page with role‑agnostic hero; courses remain main lecturer view."""
    context = {"request": request, "current_user": current_user, "error": error}
    return templates.TemplateResponse("home.html", context)


@app.on_event("startup")
def on_startup():
    """Initialize database schema and seed sample data."""
    create_db_and_tables()
    with Session(engine) as session:
        # Seed a few sample students (Sprint 1 behaviour)
        existing_student = session.exec(select(Student)).first()
        if not existing_student:
            sample_students = [
                Student(
                    name="Alice Tan",
                    email="alice.tan@example.com",
                    matric_no="SWE1001",
                ),
                Student(
                    name="Bob Lim",
                    email="bob.lim@example.com",
                    matric_no="SWE1002",
                ),
                Student(
                    name="Chong Wei",
                    email="chong.wei@example.com",
                    matric_no="SWE1003",
                ),
            ]
            session.add_all(sample_students)
            session.commit()

        # Seed a default admin user for Sprint 2 if none exists
        existing_admin = session.exec(select(User).where(User.role == "admin")).first()
        if not existing_admin:
            admin_user = User(
                name="System Admin",
                email="admin@example.com",
                password_hash=hash_password("admin123"),
                role="admin",
            )
            session.add(admin_user)
            session.commit()
            print("Seeded default admin user: admin@example.com / admin123")
