from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from src import db


app = FastAPI()

# Connect BootstrapMade assets
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

# Set template directory
templates = Jinja2Templates(directory="templates")


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ==================== ESSAY QUESTION ROUTES ====================


@app.get("/essay/add")
def add_essay_get(request: Request, success: bool = False):
    """Display the add essay question form."""
    return templates.TemplateResponse(
        "add_essay.html",
        {"request": request, "success": success},
    )


@app.post("/essay/add")
def add_essay_post(
    request: Request,
    question_text: str = Form(...),
    max_marks: int = Form(...),
):
    """Handle the submission of a new essay question."""
    # Create the question in the database
    question_id = db.create_question(question_text, max_marks)

    # Redirect to the same page with success message
    return RedirectResponse(url="/essay/add?success=true", status_code=303)


@app.get("/essay/list")
def essay_list(request: Request):
    """Display all essay questions."""
    questions = db.get_all_questions()
    return templates.TemplateResponse(
        "essay_list.html", {"request": request, "questions": questions}
    )


@app.get("/essay/grade/{question_id}")
def grade_essay_get(request: Request, question_id: int, success: bool = False):
    """Display the grading form for a specific essay question."""
    # Get the question
    question = db.get_question(question_id)

    if not question:
        return templates.TemplateResponse(
            "essay_list.html", {"request": request, "error": "Question not found"}
        )

    # For this implementation, we use a placeholder student
    student_id = "sample_student"
    student_answer = (
        "Sample student response to the essay question. This is a placeholder answer "
        "that demonstrates how the grading system works. In a real scenario, this would "
        "be the actual student's submitted essay answer."
    )

    # Check if there's an existing grade
    existing_grade = db.get_grade(question_id, student_id)

    return templates.TemplateResponse(
        "grade_essay.html",
        {
            "request": request,
            "question": question,
            "student_id": student_id,
            "student_answer": student_answer,
            "existing_grade": existing_grade,
            "success": success,
        },
    )


@app.post("/essay/grade/{question_id}")
def grade_essay_post(
    request: Request, question_id: int, marks_awarded: int = Form(...)
):
    """Handle the submission of a grade for an essay question."""
    # Get the question to validate
    question = db.get_question(question_id)

    if not question:
        return RedirectResponse(url="/essay/list", status_code=303)

    # Validate marks
    if marks_awarded < 0 or marks_awarded > question["max_marks"]:
        return RedirectResponse(url=f"/essay/grade/{question_id}", status_code=303)

    # Save the grade (using placeholder student)
    student_id = "sample_student"
    student_answer = (
        "Sample student response to the essay question. This is a placeholder answer "
        "that demonstrates how the grading system works. In a real scenario, this would "
        "be the actual student's submitted essay answer."
    )

    db.save_grade(question_id, student_id, student_answer, marks_awarded)

    # Redirect back with success message
    return RedirectResponse(url=f"/essay/grade/{question_id}?success=true", status_code=303)

