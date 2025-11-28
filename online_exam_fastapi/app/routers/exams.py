
"""Exam management routes."""


from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi import status as http_status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from datetime import datetime
from typing import Optional

from app.database import get_session
from app.deps import get_current_user, require_role
from app.models import Course, Exam, User, Enrollment, MCQQuestion, MCQAnswer, MCQResult, Student

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

STATUS_OPTIONS = ["draft", "scheduled", "completed"]

def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None

def _get_exam(exam_id: int, session: Session) -> Exam:
    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam

# ===================== SPRINT 1: STUDENT ROUTES =====================

@router.get("/schedule/student/{student_id}")
def student_exam_schedule(student_id: int, request: Request, session: Session = Depends(get_session)):
    # Get all courses student is enrolled in
    enrollments = session.exec(select(Enrollment).where(Enrollment.student_id == student_id)).all()
    course_ids = [e.course_id for e in enrollments]
    # Get all upcoming exams for these courses
    now = datetime.utcnow()
    exams = session.exec(select(Exam).where(Exam.course_id.in_(course_ids))).all()
    # Compute exam status
    exam_list = []
    for exam in exams:
        if not exam.start_time or not exam.end_time:
            status = "unscheduled"
        elif now < exam.start_time:
            mins_to_start = (exam.start_time - now).total_seconds() / 60
            if mins_to_start > 30:
                status = "upcoming"
            else:
                status = "starting soon"
        elif exam.start_time <= now <= exam.end_time:
            status = "ongoing"
        else:
            status = "ended"
        exam_list.append({"exam": exam, "status": status})
    student = session.get(Student, student_id)
    context = {"request": request, "exams": exam_list, "student": student}
    return templates.TemplateResponse("exams/schedule.html", context)


@router.get("/{exam_id}/start")
def start_exam_page(exam_id: int, request: Request, student_id: int = Query(...), session: Session = Depends(get_session)):
    exam = session.get(Exam, exam_id)
    student = session.get(Student, student_id)
    now = datetime.utcnow()
    can_start = False
    countdown = None
    if exam and exam.start_time:
        mins_to_start = (exam.start_time - now).total_seconds() / 60
        if 0 <= mins_to_start <= 30:
            can_start = True
            countdown = int((exam.start_time - now).total_seconds())
    context = {"request": request, "exam": exam, "student": student, "can_start": can_start, "countdown": countdown}
    return templates.TemplateResponse("exams/start_exam.html", context)


@router.get("/{exam_id}/join")
def join_exam(exam_id: int, request: Request, student_id: int = Query(...), session: Session = Depends(get_session)):
    exam = session.get(Exam, exam_id)
    student = session.get(Student, student_id)
    # Get MCQ questions
    questions = session.exec(select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)).all()
    # Get any existing answers
    answers = session.exec(select(MCQAnswer).where(MCQAnswer.exam_id == exam_id, MCQAnswer.student_id == student_id)).all()
    answer_map = {a.question_id: a.selected_option for a in answers}
    context = {"request": request, "exam": exam, "student": student, "questions": questions, "answer_map": answer_map}
    return templates.TemplateResponse("exams/join_exam.html", context)


@router.post("/{exam_id}/autosave")
async def autosave_answers(exam_id: int, request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    student_id = data.get("student_id")
    answers = data.get("answers", {})
    for qid, selected in answers.items():
        qid = int(qid)
        answer = session.exec(select(MCQAnswer).where(MCQAnswer.exam_id == exam_id, MCQAnswer.student_id == student_id, MCQAnswer.question_id == qid)).first()
        if answer:
            answer.selected_option = selected
            answer.saved_at = datetime.utcnow()
            session.add(answer)
        else:
            session.add(MCQAnswer(student_id=student_id, exam_id=exam_id, question_id=qid, selected_option=selected))
    session.commit()
    return {"status": "success"}


@router.post("/{exam_id}/submit")
async def submit_exam(exam_id: int, request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    student_id = data.get("student_id")
    answers = data.get("answers", {})
    # Save answers
    for qid, selected in answers.items():
        qid = int(qid)
        answer = session.exec(select(MCQAnswer).where(MCQAnswer.exam_id == exam_id, MCQAnswer.student_id == student_id, MCQAnswer.question_id == qid)).first()
        if answer:
            answer.selected_option = selected
            answer.saved_at = datetime.utcnow()
            session.add(answer)
        else:
            session.add(MCQAnswer(student_id=student_id, exam_id=exam_id, question_id=qid, selected_option=selected))
    session.commit()
    # Auto-grade
    questions = session.exec(select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)).all()
    correct = 0
    for q in questions:
        ans = session.exec(select(MCQAnswer).where(MCQAnswer.exam_id == exam_id, MCQAnswer.student_id == student_id, MCQAnswer.question_id == q.id)).first()
        if ans and ans.selected_option == q.correct_option:
            correct += 1
    total = len(questions)
    result = session.exec(select(MCQResult).where(MCQResult.exam_id == exam_id, MCQResult.student_id == student_id)).first()
    if result:
        result.score = correct
        result.total_questions = total
        result.graded_at = datetime.utcnow()
        session.add(result)
    else:
        session.add(MCQResult(student_id=student_id, exam_id=exam_id, score=correct, total_questions=total, graded_at=datetime.utcnow()))
    session.commit()
    return {"status": "graded", "score": correct, "total": total}


# ===================== SPRINT 1: LECTURER MCQ MANAGEMENT =====================

@router.get("/{exam_id}/mcq")
def list_mcqs(exam_id: int, request: Request, session: Session = Depends(get_session), current_user: User = Depends(require_role(["lecturer", "admin"]))):
    exam = session.get(Exam, exam_id)
    questions = session.exec(select(MCQQuestion).where(MCQQuestion.exam_id == exam_id)).all()
    context = {"request": request, "exam": exam, "questions": questions, "current_user": current_user}
    return templates.TemplateResponse("exams/mcq_list.html", context)


@router.get("/{exam_id}/mcq/new")
def new_mcq_form(exam_id: int, request: Request, session: Session = Depends(get_session), current_user: User = Depends(require_role(["lecturer", "admin"]))):
    exam = session.get(Exam, exam_id)
    context = {"request": request, "exam": exam, "form": None, "errors": {}, "current_user": current_user}
    return templates.TemplateResponse("exams/mcq_form.html", context)


@router.post("/{exam_id}/mcq/new")
def create_mcq(exam_id: int, request: Request, question_text: str = Form(...), option_a: str = Form(...), option_b: str = Form(...), option_c: str = Form(...), option_d: str = Form(...), correct_option: str = Form(...), session: Session = Depends(get_session), current_user: User = Depends(require_role(["lecturer", "admin"]))):
    mcq = MCQQuestion(exam_id=exam_id, question_text=question_text.strip(), option_a=option_a.strip(), option_b=option_b.strip(), option_c=option_c.strip(), option_d=option_d.strip(), correct_option=correct_option.strip())
    session.add(mcq)
    session.commit()
    return RedirectResponse(url=f"/exams/{exam_id}/mcq", status_code=http_status.HTTP_303_SEE_OTHER)


@router.get("/mcq/{question_id}/edit")
def edit_mcq_form(question_id: int, request: Request, session: Session = Depends(get_session), current_user: User = Depends(require_role(["lecturer", "admin"]))):
    mcq = session.get(MCQQuestion, question_id)
    exam = session.get(Exam, mcq.exam_id) if mcq else None
    context = {"request": request, "mcq": mcq, "exam": exam, "form": None, "errors": {}, "current_user": current_user}
    return templates.TemplateResponse("exams/mcq_form.html", context)


@router.post("/mcq/{question_id}/edit")
def update_mcq(question_id: int, request: Request, question_text: str = Form(...), option_a: str = Form(...), option_b: str = Form(...), option_c: str = Form(...), option_d: str = Form(...), correct_option: str = Form(...), session: Session = Depends(get_session), current_user: User = Depends(require_role(["lecturer", "admin"]))):
    mcq = session.get(MCQQuestion, question_id)
    if not mcq:
        raise HTTPException(status_code=404, detail="MCQ not found")
    mcq.question_text = question_text.strip()
    mcq.option_a = option_a.strip()
    mcq.option_b = option_b.strip()
    mcq.option_c = option_c.strip()
    mcq.option_d = option_d.strip()
    mcq.correct_option = correct_option.strip()
    session.add(mcq)
    session.commit()
    return RedirectResponse(url=f"/exams/{mcq.exam_id}/mcq", status_code=http_status.HTTP_303_SEE_OTHER)


@router.post("/mcq/{question_id}/delete")
def delete_mcq(question_id: int, session: Session = Depends(get_session), current_user: User = Depends(require_role(["lecturer", "admin"]))):
    mcq = session.get(MCQQuestion, question_id)
    exam_id = mcq.exam_id if mcq else None
    if mcq:
        session.delete(mcq)
        session.commit()
    return RedirectResponse(url=f"/exams/{exam_id}/mcq", status_code=http_status.HTTP_303_SEE_OTHER)


@router.get("/new")
def new_exam_form(
    request: Request,
    course_id: Optional[int] = Query(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):

    courses = session.exec(select(Course).order_by(Course.name)).all()
    context = {
        "request": request,
        "courses": courses,
        "exam": None,
        "form": None,
        "errors": {},
        # Do not preselect a course; let the user choose explicitly
        "selected_course_id": None,
        "mode": "create",
        "status_options": STATUS_OPTIONS,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/form.html", context)


# MCQ Management Menu: Select Exam for MCQ CRUD
@router.get("/mcq/menu")
def mcq_menu(request: Request, session: Session = Depends(get_session), current_user: User = Depends(require_role(["lecturer", "admin"]))):
    exams = session.exec(select(Exam)).all()
    context = {"request": request, "exams": exams, "current_user": current_user}
    return templates.TemplateResponse("exams/mcq_menu.html", context)


@router.post("/new")
def create_exam(
    request: Request,
    title: str = Form(...),
    subject: str = Form(...),
    duration_minutes: str = Form(...),
    course_id: str = Form(...),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    instructions: Optional[str] = Form(None),
    status: str = Form("draft"),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    errors: dict[str, str] = {}

    title_clean = title.strip()
    subject_clean = subject.strip()
    instructions_clean = (instructions or "").strip()

    # Required text fields
    if not title_clean:
        errors["title"] = "Exam title is required."
    if not subject_clean:
        errors["subject"] = "Exam subject is required."

    # Duration validation
    try:
        duration_value = int(duration_minutes)
        if duration_value <= 0:
            errors["duration_minutes"] = "Duration must be greater than zero."
    except (TypeError, ValueError):
        errors["duration_minutes"] = "Duration must be a valid number of minutes."
        duration_value = 0

    # Course validation
    course_id_int: Optional[int] = None
    if not course_id:
        errors["course_id"] = "Please select a course for this exam."
    else:
        try:
            course_id_int = int(course_id)
        except (TypeError, ValueError):
            errors["course_id"] = "Please select a valid course."
        else:
            course = session.get(Course, course_id_int)
            if not course:
                errors["course_id"] = "Selected course does not exist."

    # Datetime validation
    if not start_time:
        errors["start_time"] = "Exam start time is required."
        start_dt = None
    else:
        try:
            start_dt = _parse_datetime(start_time)
        except ValueError:
            start_dt = None
            errors["start_time"] = "Start time format is invalid."

    if not end_time:
        errors["end_time"] = "Exam end time is required."
        end_dt = None
    else:
        try:
            end_dt = _parse_datetime(end_time)
        except ValueError:
            end_dt = None
            errors["end_time"] = "End time format is invalid."

    if start_dt and end_dt and end_dt <= start_dt:
        errors["end_time"] = "End time must be after the start time."

    # Status validation
    status_clean = (status or "").strip().lower()
    if status_clean not in STATUS_OPTIONS:
        errors["status"] = "Please select a valid status."

    if errors:
        courses = session.exec(select(Course).order_by(Course.name)).all()
        form = {
            "title": title,
            "subject": subject,
            "duration_minutes": duration_minutes,
            "course_id": course_id,
            "start_time": start_time or "",
            "end_time": end_time or "",
            "instructions": instructions_clean,
            "status": status_clean or "draft",
        }
        context = {
            "request": request,
            "courses": courses,
            "exam": None,
            "form": form,
            "errors": errors,
            "selected_course_id": int(course_id) if course_id else None,
            "mode": "create",
            "status_options": STATUS_OPTIONS,
            "current_user": current_user,
        }
        return templates.TemplateResponse(
            "exams/form.html", context, status_code=http_status.HTTP_400_BAD_REQUEST
        )

    exam = Exam(
        title=title_clean,
        subject=subject_clean,
        duration_minutes=duration_value,
        course_id=course_id_int if course_id_int is not None else None,
        start_time=start_dt,
        end_time=end_dt,
        instructions=instructions_clean or None,
        status=status_clean,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(exam)
    session.commit()
    session.refresh(exam)
    return RedirectResponse(
        url=f"/exams/{exam.id}", status_code=http_status.HTTP_303_SEE_OTHER
    )


@router.get("/course/{course_id}")
def exams_for_course(
    course_id: int,
    request: Request,
    sort: Optional[str] = Query("start"),
    direction: Optional[str] = Query("asc"),
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List all exams associated with a specific course, with optional sorting."""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    exams = session.exec(select(Exam).where(Exam.course_id == course_id)).all()

    key_map = {
        "title": lambda e: e.title or "",
        "subject": lambda e: e.subject or "",
        "start": lambda e: e.start_time or datetime.max,
        "end": lambda e: e.end_time or datetime.max,
        "duration": lambda e: e.duration_minutes or 0,
        "status": lambda e: (e.status or "").lower(),
    }

    sort_key = key_map.get(sort or "start", key_map["start"])
    is_desc = (direction or "asc").lower() == "desc"
    exams_sorted = sorted(exams, key=sort_key, reverse=is_desc)

    has_sort = (sort not in (None, "", "start")) or (
        (direction or "asc").lower() != "asc"
    )

    context = {
        "request": request,
        "course": course,
        "exams": exams_sorted,
        "sort": sort,
        "direction": "desc" if is_desc else "asc",
        "has_sort": has_sort,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/list_by_course.html", context)


@router.get("/{exam_id}")
def exam_detail(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    exam = _get_exam(exam_id, session)
    course = session.get(Course, exam.course_id) if exam.course_id else None
    context = {
        "request": request,
        "exam": exam,
        "course": course,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/detail.html", context)


@router.get("/{exam_id}/edit")
def edit_exam_form(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    exam = _get_exam(exam_id, session)
    courses = session.exec(select(Course).order_by(Course.name)).all()
    context = {
        "request": request,
        "exam": exam,
        "form": None,
        "errors": {},
        "courses": courses,
        "selected_course_id": exam.course_id,
        "mode": "edit",
        "status_options": STATUS_OPTIONS,
        "current_user": current_user,
    }
    return templates.TemplateResponse("exams/form.html", context)


@router.post("/{exam_id}/edit")
def update_exam(
    exam_id: int,
    request: Request,
    title: str = Form(...),
    subject: str = Form(...),
    duration_minutes: str = Form(...),
    course_id: str = Form(...),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    instructions: Optional[str] = Form(None),
    status: str = Form("draft"),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    exam = _get_exam(exam_id, session)

    errors: dict[str, str] = {}

    title_clean = title.strip()
    subject_clean = subject.strip()
    instructions_clean = (instructions or "").strip()

    if not title_clean:
        errors["title"] = "Exam title is required."
    if not subject_clean:
        errors["subject"] = "Exam subject is required."

    try:
        duration_value = int(duration_minutes)
        if duration_value <= 0:
            errors["duration_minutes"] = "Duration must be greater than zero."
    except (TypeError, ValueError):
        errors["duration_minutes"] = "Duration must be a valid number of minutes."
        duration_value = 0

    course_id_int: Optional[int] = None
    if not course_id:
        errors["course_id"] = "Please select a course for this exam."
    else:
        try:
            course_id_int = int(course_id)
        except (TypeError, ValueError):
            errors["course_id"] = "Please select a valid course."
        else:
            course = session.get(Course, course_id_int)
            if not course:
                errors["course_id"] = "Selected course does not exist."

    if not start_time:
        errors["start_time"] = "Exam start time is required."
        start_dt = None
    else:
        try:
            start_dt = _parse_datetime(start_time)
        except ValueError:
            start_dt = None
            errors["start_time"] = "Start time format is invalid."

    if not end_time:
        errors["end_time"] = "Exam end time is required."
        end_dt = None
    else:
        try:
            end_dt = _parse_datetime(end_time)
        except ValueError:
            end_dt = None
            errors["end_time"] = "End time format is invalid."

    if start_dt and end_dt and end_dt <= start_dt:
        errors["end_time"] = "End time must be after the start time."

    status_clean = (status or "").strip().lower()
    if status_clean not in STATUS_OPTIONS:
        errors["status"] = "Please select a valid status."

    if errors:
        courses = session.exec(select(Course).order_by(Course.name)).all()
        form = {
            "title": title,
            "subject": subject,
            "duration_minutes": duration_minutes,
            "course_id": course_id,
            "start_time": start_time or "",
            "end_time": end_time or "",
            "instructions": instructions_clean,
            "status": status_clean or exam.status,
        }
        context = {
            "request": request,
            "exam": exam,
            "form": form,
            "errors": errors,
            "courses": courses,
            "selected_course_id": int(course_id) if course_id else None,
            "mode": "edit",
            "status_options": STATUS_OPTIONS,
            "current_user": current_user,
        }
        return templates.TemplateResponse(
            "exams/form.html", context, status_code=http_status.HTTP_400_BAD_REQUEST
        )

    exam.title = title_clean
    exam.subject = subject_clean
    exam.duration_minutes = duration_value
    exam.course_id = course_id_int if course_id_int is not None else None
    exam.start_time = start_dt
    exam.end_time = end_dt
    exam.instructions = instructions_clean or None
    exam.status = status_clean
    exam.updated_at = datetime.utcnow()

    session.add(exam)
    session.commit()

    return RedirectResponse(
        url=f"/exams/{exam.id}", status_code=http_status.HTTP_303_SEE_OTHER
    )
