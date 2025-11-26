"""
FastAPI Main Application
Online Examination & Grading System - Sprint 1

Sprint 1 Features:
1. Create Essay Questions
2. Manual Grade Essay Questions
3. Auto Submit When Time Ends
4. One Attempt Enforcement

Sprint 2: Add authentication, role-based access, real-time features
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from app.database import create_db_and_tables
from app.routers import essay, exam_taking, grading

# Initialize FastAPI app
app = FastAPI(
    title="Online Examination & Grading System",
    description="Sprint 1: Essay Questions, Manual Grading, Auto-Submit, One Attempt",
    version="1.0.0"
)

# Mount static files (CSS, JS, images from BootstrapMade template)
# Use assets folder for BootstrapMade template files
app.mount("/static", StaticFiles(directory="assets"), name="static")

# Configure Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(
    essay.router,
    prefix="/essays",
    tags=["Essay Questions"]
)

app.include_router(
    exam_taking.router,
    prefix="/exam",
    tags=["Exam Taking"]
)

app.include_router(
    grading.router,
    prefix="/grading",
    tags=["Manual Grading"]
)


@app.on_event("startup")
def on_startup():
    """
    Create database tables on application startup.
    Sprint 2: Add database migration system (Alembic)
    """
    create_db_and_tables()


@app.get("/")
def home(request: Request):
    """
    Home page - Dashboard
    Sprint 1: Simple landing page
    Sprint 2: Role-based dashboard (student/lecturer views)
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.get("/health")
def health_check():
    """
    Health check endpoint for monitoring.
    Sprint 2: Add database connectivity check
    """
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/test")
def test_route():
    """Test route to verify server is responding"""
    return {"message": "Server is working!", "templates_dir": "app/templates", "static_dir": "assets"}


# Sprint 2: Add these routes
# - /auth/login (authentication)
# - /auth/logout
# - /exams (list all exams)
# - /exams/create (create new exam)
# - /dashboard/student (student dashboard)
# - /dashboard/lecturer (lecturer dashboard)
# - /reports (grading reports and analytics)
