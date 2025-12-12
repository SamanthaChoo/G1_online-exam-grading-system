from app.database import get_session
from app.models import (
    EssayAnswer,
    Exam,
    ExamAttempt,
    ExamQuestion,
    Student,
    User,
    Enrollment,
)
from app.services.essay_service import (
    add_question,
    delete_question,
    edit_question,
    get_question,
    grade_attempt,
    start_attempt,
    submit_answers,
    timeout_attempt,
)
from datetime import timezone
from fastapi import APIRouter, Depends, Form, Request, Query, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.deps import require_login, get_current_user


def _exam_has_answers(session: Session, exam_id: int) -> bool:
    """Check if an exam has any essay answers linked to its questions."""
    questions = session.exec(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
    ).all()
    for question in questions:
        answer = session.exec(
            select(EssayAnswer).where(EssayAnswer.question_id == question.id)
        ).first()
        if answer:
            return True
    return False


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/essay")
def essay_index(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
):
    exams = session.exec(select(Exam)).all()
    # Build metadata for each exam indicating whether it has any questions.
    exams_meta = []
    for ex in exams:
        has_q = (
            session.exec(
                select(ExamQuestion).where(ExamQuestion.exam_id == ex.id)
            ).first()
            is not None
        )
        exams_meta.append({"exam": ex, "has_questions": has_q})
    return templates.TemplateResponse(
        "essay/index.html",
        {"request": request, "exams_meta": exams_meta, "current_user": current_user},
    )


@router.get("/essay/{exam_id}/questions")
def essay_questions(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
):
    exam = session.get(Exam, exam_id)
    qs = session.exec(select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)).all()
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        "essay/questions.html",
        {
            "request": request,
            "exam": exam,
            "questions": qs,
            "error": error,
            "current_user": current_user,
        },
    )


@router.get("/essay/questions/select")
def select_exam_for_question(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
):
    """Show a list of exams so a lecturer can pick one before adding questions.

    Students are not allowed to access this page; we surface a friendly error
    message instead of the selection form when blocked.
    """
    exams = session.exec(select(Exam)).all()
    # If the current user is a student, do not show the selection form
    if current_user and current_user.role == "student":
        return templates.TemplateResponse(
            "essay/select_exam.html",
            {
                "request": request,
                "exams": exams,
                "error": "Students are not allowed to create questions.",
            },
        )
    return templates.TemplateResponse(
        "essay/select_exam.html", {"request": request, "exams": exams}
    )


@router.post("/essay/questions/select")
def select_exam_for_question_submit(exam_id: int = Form(...)):
    return RedirectResponse(url=f"/essay/{exam_id}/questions/new", status_code=303)


@router.get("/essay/questions/new")
def new_question_select_redirect(
    request: Request, session: Session = Depends(get_session)
):
    """Ensure the user is always prompted to select an exam first.

    The UI should require selecting an exam before showing the create-question
    form (even if there is only one exam). This route redirects to the
    selection page.
    """
    return RedirectResponse(url="/essay/questions/select", status_code=303)


@router.get("/essay/{exam_id}/questions/new")
def new_question_form(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
):
    exam = session.get(Exam, exam_id)
    # Students should not be able to open the create-question page
    if current_user and current_user.role == "student":
        return templates.TemplateResponse(
            "essay/new_question.html",
            {
                "request": request,
                "exam": exam,
                "error": "Students are not allowed to create questions.",
            },
        )
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
    try:
        add_question(session, exam_id, question_text, max_marks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/essay/{exam_id}/questions", status_code=303)


@router.get("/essay/{exam_id}/questions/{question_id}/edit")
def edit_question_form(
    exam_id: int,
    question_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
):
    exam = session.get(Exam, exam_id)
    question = get_question(session, question_id)

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Check if exam has any answers - prevent editing if it does
    if _exam_has_answers(session, exam_id):
        return templates.TemplateResponse(
            "essay/edit_question.html",
            {
                "request": request,
                "exam": exam,
                "question": question,
                "error": "Cannot edit questions after students have submitted answers.",
                "current_user": current_user,
            },
        )

    # Students should not be able to edit questions
    if current_user and current_user.role == "student":
        return templates.TemplateResponse(
            "essay/edit_question.html",
            {
                "request": request,
                "exam": exam,
                "question": question,
                "error": "Students are not allowed to edit questions.",
                "current_user": current_user,
            },
        )

    return templates.TemplateResponse(
        "essay/edit_question.html",
        {
            "request": request,
            "exam": exam,
            "question": question,
            "current_user": current_user,
        },
    )


@router.post("/essay/{exam_id}/questions/{question_id}/edit")
def update_question(
    exam_id: int,
    question_id: int,
    question_text: str = Form(None),
    max_marks: int = Form(None),
    session: Session = Depends(get_session),
):
    # Check if exam has any answers - prevent editing if it does
    if _exam_has_answers(session, exam_id):
        raise HTTPException(
            status_code=400,
            detail="Cannot edit questions after students have submitted answers.",
        )

    try:
        edit_question(session, question_id, question_text, max_marks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/essay/{exam_id}/questions", status_code=303)


@router.post("/essay/{exam_id}/questions/{question_id}/delete")
def delete_question_ui(
    exam_id: int,
    question_id: int,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
):
    # Students should not be able to delete questions
    if current_user and current_user.role == "student":
        return RedirectResponse(
            url=f"/essay/{exam_id}/questions?error=Students+are+not+allowed+to+delete+questions.",
            status_code=303,
        )

    # Check if exam has any answers - prevent deleting if it does
    if _exam_has_answers(session, exam_id):
        return RedirectResponse(
            url=f"/essay/{exam_id}/questions?error=Cannot+delete+questions+after+students+have+submitted+answers.",
            status_code=303,
        )

    try:
        delete_question(session, question_id)
    except ValueError as e:
        return RedirectResponse(
            url=f"/essay/{exam_id}/questions?error={str(e).replace(' ', '+')}",
            status_code=303,
        )
    return RedirectResponse(url=f"/essay/{exam_id}/questions", status_code=303)


@router.get("/essay/{exam_id}/attempts")
def list_attempts(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
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

    # If a student is viewing, show only their attempts and hide grading controls
    if current_user and current_user.role == "student":
        # find student id
        student_id = current_user.student_id
        if student_id is None:
            s = session.exec(
                select(Student).where(Student.user_id == current_user.id)
            ).first()
            student_id = s.id if s else None
        filtered = [
            x for x in attempts_with_stats if x["attempt"].student_id == student_id
        ]
        return templates.TemplateResponse(
            "essay/attempts.html",
            {
                "request": request,
                "exam": exam,
                "attempts_with_stats": filtered,
                "current_user": current_user,
            },
        )

    return templates.TemplateResponse(
        "essay/attempts.html",
        {
            "request": request,
            "exam": exam,
            "attempts_with_stats": attempts_with_stats,
            "current_user": current_user,
        },
    )


@router.post("/essay/{exam_id}/start")
def start_submit(
    exam_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_login),
):
    # Only students may start an attempt
    if current_user.role != "student":
        return RedirectResponse(url=f"/essay/{exam_id}/start", status_code=303)

    # Resolve the Student.id linked to this user
    student_id = current_user.student_id
    if student_id is None:
        s = session.exec(
            select(Student).where(Student.user_id == current_user.id)
        ).first()
        if s:
            student_id = s.id

    if student_id is None:
        # No linked student record - cannot start attempt
        return RedirectResponse(
            url=f"/essay/{exam_id}/start?no_student=true", status_code=303
        )

    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if exam.course_id:
        enrollment = session.exec(
            select(Enrollment).where(
                Enrollment.course_id == exam.course_id,
                Enrollment.student_id == student_id,
            )
        ).first()
        if enrollment is None:
            raise HTTPException(
                status_code=403, detail="You are not enrolled in this course."
            )

    attempt = start_attempt(session, exam_id, student_id)
    # If the returned attempt is not in-progress it means the student already
    # has a final attempt (submitted/timed_out). Stay on start page and show an error.
    if attempt and attempt.status != "in_progress":
        return RedirectResponse(
            url=f"/essay/{exam_id}/start?already=true", status_code=303
        )

    return RedirectResponse(
        url=f"/essay/{exam_id}/attempt/{attempt.id}", status_code=303
    )


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
    # Compute how many attempts this student has for this exam — used by UI to warn
    attempts_count = 0
    if attempt and attempt.student_id is not None:
        attempts_for_student = session.exec(
            select(ExamAttempt).where(
                (ExamAttempt.exam_id == exam_id)
                & (ExamAttempt.student_id == attempt.student_id)
            )
        ).all()
        attempts_count = len(attempts_for_student)
    # Provide a timezone-safe epoch-millisecond for JS to construct Date()
    started_at_ms = None
    if attempt and getattr(attempt, "started_at", None):
        try:
            sat = attempt.started_at
            # If the datetime is naive, assume it is UTC (the app uses UTC by default).
            if sat.tzinfo is None:
                sat = sat.replace(tzinfo=timezone.utc)
            started_at_ms = int(sat.timestamp() * 1000)
        except Exception:
            started_at_ms = None
    return templates.TemplateResponse(
        "essay/attempt.html",
        {
            "request": request,
            "exam": exam,
            "attempt": attempt,
            "questions": questions,
            "answers_map": answers_map,
            "attempts_count": attempts_count,
            "started_at_ms": started_at_ms,
        },
    )


@router.get("/essay/{exam_id}/attempt/{attempt_id}/auto_submitted")
def attempt_auto_submitted(
    exam_id: int,
    attempt_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    exam = session.get(Exam, exam_id)
    attempt = session.get(ExamAttempt, attempt_id)
    return templates.TemplateResponse(
        "essay/auto_submitted.html",
        {"request": request, "exam": exam, "attempt": attempt},
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
    # After a normal submit, show a friendly confirmation page
    return RedirectResponse(
        url=f"/essay/{exam_id}/attempt/{attempt_id}/submitted", status_code=303
    )


@router.get("/essay/{exam_id}/attempt/{attempt_id}/submitted")
def attempt_submitted(
    exam_id: int,
    attempt_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    exam = session.get(Exam, exam_id)
    attempt = session.get(ExamAttempt, attempt_id)
    return templates.TemplateResponse(
        "essay/submitted.html", {"request": request, "exam": exam, "attempt": attempt}
    )


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

    # After a timeout, show an auto-submitted confirmation page
    return RedirectResponse(
        url=f"/essay/{exam_id}/attempt/{attempt_id}/auto_submitted", status_code=303
    )


@router.get("/essay/{exam_id}/grade/{attempt_id}")
def grade_form(
    exam_id: int,
    attempt_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
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

    # Check if all answers are graded (all have marks_awarded set)
    is_graded = all(a.marks_awarded is not None for a in answers) if answers else False

    # Calculate total marks
    total_possible = sum(q.max_marks or 0 for q in questions)
    total_current = sum(
        (answers_map.get(q.id).marks_awarded or 0) if answers_map.get(q.id) else 0
        for q in questions
    )

    return templates.TemplateResponse(
        "essay/grade.html",
        {
            "request": request,
            "exam": exam,
            "attempt": attempt,
            "questions": questions,
            "answers_map": answers_map,
            "student": student,
            "is_graded": is_graded,
            "current_user": current_user,
            "total_possible": total_possible,
            "total_current": total_current,
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
    feedback_list = []
    for key, value in form.items():
        if key.startswith("score_"):
            try:
                qid = int(key.split("_")[1])
            except Exception:
                continue
            try:
                marks = float(value)
            except Exception:
                marks = 0
            scores.append({"question_id": qid, "marks": marks})
        elif key.startswith("feedback_"):
            try:
                qid = int(key.split("_")[1])
            except Exception:
                continue
            feedback_list.append({"question_id": qid, "feedback": value})

    try:
        result = grade_attempt(session, attempt_id, scores, feedback_list)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
                "feedback": ans.grader_feedback if ans else None,
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


# TODO: Anti-cheating activity logging endpoint disabled pending ExamActivityLog model implementation
# @router.post("/essay/{exam_id}/log-activity")
# async def log_essay_activity(
#     exam_id: int,
#     request: Request,
#     session: Session = Depends(get_session)
# ):
#     """Log suspicious activities during essay exam taking for anti-cheating purposes."""
#     data = await request.json()
#     student_id = data.get("student_id")
#     attempt_id = data.get("attempt_id")  # Required for essay attempts
#     activity_type = data.get("activity_type")
#     metadata = data.get("metadata")  # Optional JSON string or dict
#     severity = data.get("severity", "low")  # low, medium, high
#
#     if not student_id or not activity_type:
#         return {"status": "error", "message": "student_id and activity_type are required"}
#
#     # Validate exam exists
#     exam = session.get(Exam, exam_id)
#     if not exam:
#         return {"status": "error", "message": "Exam not found"}
#
#     # Validate student exists
#     student = session.get(Student, student_id)
#     if not student:
#         return {"status": "error", "message": "Student not found"}
#
#     # Convert metadata to JSON string if it's a dict
#     metadata_str = None
#     if metadata:
#         if isinstance(metadata, dict):
#             metadata_str = json.dumps(metadata)
#         else:
#             metadata_str = str(metadata)
#
#     # Create activity log entry
#     # activity_log = ExamActivityLog(
#     #     exam_id=exam_id,
#     #     student_id=student_id,
#     #     attempt_id=attempt_id,
#     #     activity_type=activity_type,
#     #     activity_metadata=metadata_str,
#     #     severity=severity,
#     #     timestamp=datetime.utcnow()
#     # )
#     # session.add(activity_log)
#     # session.commit()
#
#     # return {"status": "success", "log_id": activity_log.id}
