"""FastAPI entrypoint for the Online Examination & Grading System."""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine, get_session
from app.models import Student
from app.routers import courses as courses_router_module
from app.routers import exams as exams_router_module

app = FastAPI(title="Online Examination & Grading System")

# Static + templates configuration
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Routers
app.include_router(courses_router_module.router, prefix="/courses", tags=["courses"])
app.include_router(exams_router_module.router, prefix="/exams", tags=["exams"])


@app.get("/")
def root():
    """Redirect root requests to the courses listing page."""
    return RedirectResponse(url="/courses/")


@app.on_event("startup")
def on_startup():
    """Initialize database schema and seed sample data."""
    create_db_and_tables()
    with Session(engine) as session:
        existing_student = session.exec(select(Student)).first()
        if not existing_student:
            sample_students = [
                Student(name="Alice Tan", email="alice.tan@example.com", matric_no="SWE1001"),
                Student(name="Bob Lim", email="bob.lim@example.com", matric_no="SWE1002"),
                Student(name="Chong Wei", email="chong.wei@example.com", matric_no="SWE1003"),
            ]
            session.add_all(sample_students)
            session.commit()

