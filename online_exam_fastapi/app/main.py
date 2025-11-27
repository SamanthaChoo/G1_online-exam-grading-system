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
from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(title="Online Examination & Grading System")


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
templates = Jinja2Templates(directory="app/templates")

# Routers
app.include_router(auth_router_module.router, prefix="/auth", tags=["auth"])
app.include_router(admin_router_module.router, prefix="/admin", tags=["admin"])
app.include_router(courses_router_module.router, prefix="/courses", tags=["courses"])
app.include_router(exams_router_module.router, prefix="/exams", tags=["exams"])
app.include_router(essay_router_module.router)
app.include_router(essay_ui_router.router)


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
