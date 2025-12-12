"""Lecturer routes for managing exams and viewing results."""

from typing import Optional
from app.database import get_session
from app.deps import require_role
from app.models import (
    User,
    Course,
    Exam,
    CourseLecturer,
    ExamAttempt,
    EssayAnswer,
    MCQResult,
    Student,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/results")
def view_results_by_course(
    request: Request,
    course_id: Optional[int] = Query(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(["lecturer", "admin"])),
):
    """View exam results grouped by course for a lecturer."""

    # Get all courses assigned to this lecturer (or all courses if admin)
    if current_user.role == "admin":
        courses = session.exec(select(Course).order_by(Course.name)).all()
    else:
        # Get courses where this lecturer is assigned
        lecturer_courses = session.exec(
            select(CourseLecturer).where(CourseLecturer.lecturer_id == current_user.id)
        ).all()
        course_ids = [lc.course_id for lc in lecturer_courses]
        if course_ids:
            courses = session.exec(
                select(Course).where(Course.id.in_(course_ids)).order_by(Course.name)
            ).all()
        else:
            courses = []

    selected_course = None
    grouped_results = []

    if course_id:
        # Verify lecturer has access to this course
        selected_course = session.get(Course, course_id)
        if not selected_course:
            raise HTTPException(status_code=404, detail="Course not found")

        if current_user.role != "admin":
            lecturer_course = session.exec(
                select(CourseLecturer).where(
                    (CourseLecturer.lecturer_id == current_user.id)
                    & (CourseLecturer.course_id == course_id)
                )
            ).first()
            if not lecturer_course:
                raise HTTPException(
                    status_code=403, detail="You don't have access to this course"
                )

        # Get all exams for this course
        exams = session.exec(
            select(Exam).where(Exam.course_id == course_id).order_by(Exam.title)
        ).all()

        # Group results by exam
        for exam in exams:
            exam_data = {"exam": exam, "students": []}

            # Get all attempts for this exam
            attempts = session.exec(
                select(ExamAttempt).where(ExamAttempt.exam_id == exam.id)
            ).all()

            for attempt in attempts:
                student = session.get(Student, attempt.student_id)
                if not student:
                    continue

                # Get MCQ results if any
                mcq_result = session.exec(
                    select(MCQResult).where(
                        (MCQResult.student_id == attempt.student_id)
                        & (MCQResult.exam_id == exam.id)
                    )
                ).first()

                # Get essay answers if any
                essay_answers = session.exec(
                    select(EssayAnswer).where(EssayAnswer.attempt_id == attempt.id)
                ).all()

                # Calculate essay total
                essay_total = (
                    sum((ans.marks_awarded or 0) for ans in essay_answers)
                    if essay_answers
                    else None
                )

                student_result = {
                    "student": student,
                    "attempt": attempt,
                    "mcq_result": mcq_result,
                    "essay_answers": essay_answers,
                    "essay_total": essay_total,
                }

                exam_data["students"].append(student_result)

            if exam_data["students"]:  # Only include exams that have submissions
                grouped_results.append(exam_data)

    context = {
        "request": request,
        "courses": courses,
        "selected_course": selected_course,
        "grouped_results": grouped_results,
        "current_user": current_user,
    }

    return templates.TemplateResponse("lecturer/results_by_course.html", context)
