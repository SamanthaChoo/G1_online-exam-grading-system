from app.database import get_session
from app.models import EssayAnswer, Exam, ExamAttempt, ExamQuestion, Student
from app.services.essay_service import (
    add_question,
    grade_attempt,
    start_attempt,
    submit_answers,
    timeout_attempt,
)
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/essay")
def essay_index(request: Request, session: Session = Depends(get_session)):
    exams = session.exec(select(Exam)).all()
    return templates.TemplateResponse(
        "essay/index.html", {"request": request, "exams": exams}
    )


@router.get("/essay/{exam_id}/questions")
def essay_questions(
    exam_id: int, request: Request, session: Session = Depends(get_session)
):
    exam = session.get(Exam, exam_id)
    qs = session.exec(select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)).all()
    return templates.TemplateResponse(
        "essay/questions.html", {"request": request, "exam": exam, "questions": qs}
    )


@router.get("/essay/{exam_id}/questions/new")
def new_question_form(
    exam_id: int, request: Request, session: Session = Depends(get_session)
):
    exam = session.get(Exam, exam_id)
    return templates.TemplateResponse(
        "essay/new_question.html", {"request": request, "exam": exam}
    )


@router.post("/essay/{exam_id}/questions/new")
def create_question(
    exam_id: int,
    question_text: str = Form(...),
    max_marks: int = Form(...),
    session: Session = Depends(get_session),
):
    add_question(session, exam_id, question_text, max_marks)
    return RedirectResponse(url=f"/essay/{exam_id}/questions", status_code=303)


@router.get("/essay/{exam_id}/attempts")
def list_attempts(
    exam_id: int, request: Request, session: Session = Depends(get_session)
):
    attempts = session.exec(
        select(ExamAttempt).where(ExamAttempt.exam_id == exam_id)
    ).all()
    exam = session.get(Exam, exam_id)

    # Prepare per-attempt stats: number of questions, graded count, total score
    questions = session.exec(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
    ).all()
    total_questions = len(questions)
    total_possible = sum((q.max_marks or 0) for q in questions)

    attempts_with_stats = []
    for a in attempts:
        ans = session.exec(
            select(EssayAnswer).where(EssayAnswer.attempt_id == a.id)
        ).all()
        graded_count = sum(1 for x in ans if x.marks_awarded is not None)
        score = sum((x.marks_awarded or 0) for x in ans)
        attempts_with_stats.append(
            {
                "attempt": a,
                "graded_count": graded_count,
                "total_questions": total_questions,
                "score": score,
                "total_possible": total_possible,
            }
        )

    return templates.TemplateResponse(
        "essay/attempts.html",
        {"request": request, "exam": exam, "attempts_with_stats": attempts_with_stats},
    )


@router.get("/essay/{exam_id}/start")
def start_form(exam_id: int, request: Request, session: Session = Depends(get_session)):
    exam = session.get(Exam, exam_id)
    return templates.TemplateResponse(
        "essay/start.html", {"request": request, "exam": exam}
    )


@router.post("/essay/{exam_id}/start")
def start_submit(
    exam_id: int, student_id: int = Form(...), session: Session = Depends(get_session)
):
    attempt = start_attempt(session, exam_id, student_id)
    # If the returned attempt is not in-progress it means the student already
    # has a final attempt (submitted/timed_out). Redirect to attempts list.
    if attempt and attempt.status != "in_progress":
        return RedirectResponse(url=f"/essay/{exam_id}/attempts?already=true", status_code=303)

    return RedirectResponse(url=f"/essay/{exam_id}/attempt/{attempt.id}", status_code=303)


@router.get("/essay/{exam_id}/attempt/{attempt_id}")
def attempt_view(
    exam_id: int,
    attempt_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    exam = session.get(Exam, exam_id)
    attempt = session.get(ExamAttempt, attempt_id)
    questions = session.exec(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
    ).all()
    answers = session.exec(
        select(EssayAnswer).where(EssayAnswer.attempt_id == attempt_id)
    ).all()
    answers_map = {a.question_id: a for a in answers}
    return templates.TemplateResponse(
        "essay/attempt.html",
        {
            "request": request,
            "exam": exam,
            "attempt": attempt,
            "questions": questions,
            "answers_map": answers_map,
        },
    )


@router.post("/essay/{exam_id}/attempt/{attempt_id}/submit")
async def attempt_submit(
    exam_id: int,
    attempt_id: int,
    session: Session = Depends(get_session),
    request: Request = None,
):
    # Read form fields from request asynchronously
    form = await request.form()
    # collect answers from fields named answer_{qid}
    answers = []
    for key, value in form.items():
        if key.startswith("answer_"):
            try:
                qid = int(key.split("_", 1)[1])
            except Exception:
                continue
            answers.append({"question_id": qid, "answer_text": value})

    # find student_id from attempt record
    attempt = session.get(ExamAttempt, attempt_id)
    student_id = attempt.student_id if attempt else None
    if student_id is not None:
        submit_answers(session, exam_id, student_id, answers)

    return RedirectResponse(url=f"/essay/{exam_id}/attempts", status_code=303)


@router.post("/essay/{exam_id}/attempt/{attempt_id}/timeout")
async def attempt_timeout(
    exam_id: int,
    attempt_id: int,
    session: Session = Depends(get_session),
    request: Request = None,
):
    # Accept JSON body with answers; fall back to empty dict
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    answers = payload.get("answers") or {}

    # find student_id from attempt record
    attempt = session.get(ExamAttempt, attempt_id)
    student_id = attempt.student_id if attempt else None

    if student_id is not None:
        # timeout_attempt will record answers and mark attempt timed out
        timed = timeout_attempt(session, exam_id, student_id, answers)
        if not timed:
            return RedirectResponse(url=f"/essay/{exam_id}/attempts", status_code=303)

    return RedirectResponse(url=f"/essay/{exam_id}/attempt/{attempt_id}", status_code=303)


@router.get("/essay/{exam_id}/grade/{attempt_id}")
def grade_form(
    exam_id: int,
    attempt_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    exam = session.get(Exam, exam_id)
    attempt = session.get(ExamAttempt, attempt_id)
    questions = session.exec(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
    ).all()
    answers = session.exec(
        select(EssayAnswer).where(EssayAnswer.attempt_id == attempt_id)
    ).all()
    answers_map = {a.question_id: a for a in answers}
    # lookup student name if available for clearer UI
    student = None
    if attempt and attempt.student_id is not None:
        student = session.get(Student, attempt.student_id)

    return templates.TemplateResponse(
        "essay/grade.html",
        {
            "request": request,
            "exam": exam,
            "attempt": attempt,
            "questions": questions,
            "answers_map": answers_map,
            "student": student,
        },
    )


@router.post("/essay/{exam_id}/grade/{attempt_id}")
async def grade_submit(
    exam_id: int,
    attempt_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    form = await request.form()
    # collect scores
    scores = []
    for key, value in form.items():
        if key.startswith("score_"):
            try:
                qid = int(key.split("_")[1])
            except Exception:
                continue
            try:
                marks = int(value)
            except Exception:
                marks = 0
            scores.append({"question_id": qid, "marks": marks})
    result = grade_attempt(session, attempt_id, scores)
    # Build per-question breakdown to show on result page
    qlist = session.exec(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
    ).all()
    answers = session.exec(
        select(EssayAnswer).where(EssayAnswer.attempt_id == attempt_id)
    ).all()
    answers_map = {a.question_id: a for a in answers}
    breakdown = []
    for q in qlist:
        ans = answers_map.get(q.id)
        breakdown.append(
            {
                "question_id": q.id,
                "question_text": q.question_text,
                "max_marks": q.max_marks,
                "marks_awarded": (
                    ans.marks_awarded if ans and ans.marks_awarded is not None else 0
                ),
            }
        )

    return templates.TemplateResponse(
        "essay/grade_result.html",
        {
            "request": request,
            "attempt_id": result.get("attempt_id"),
            "total_marks": result.get("total_marks"),
            "answers_graded": result.get("answers_graded"),
            "breakdown": breakdown,
        },
    )
