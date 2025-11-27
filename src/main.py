from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

# Import routers
from app.routers import questions, exam_execution
from app.database import init_db

# Get the project root directory (parent of src)
BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI
    Initializes database on startup
    """
    # Startup: Initialize database
    init_db()
    print("✅ Database initialized successfully")
    yield
    # Shutdown: cleanup if needed
    print("🔴 Application shutting down")


app = FastAPI(
    title="Online Exam & Grading System",
    description="Sprint 1: MCQ Management + Auto-Grading + Exam Execution",
    version="1.0.0",
    lifespan=lifespan
)

# Connect BootstrapMade assets (use absolute path)
app.mount("/assets", StaticFiles(directory=str(BASE_DIR / "assets")), name="assets")

# Set template directory (use absolute path)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Include routers
app.include_router(questions.router, prefix="/questions", tags=["MCQ Questions"])
app.include_router(exam_execution.router, prefix="/exam", tags=["Exam Execution"])


@app.get("/")
def home(request: Request):
    """
    Home page
    """
    return templates.TemplateResponse("index.html", {"request": request})
