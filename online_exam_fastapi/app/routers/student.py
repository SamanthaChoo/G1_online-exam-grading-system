"""Student-facing routes for viewing grades, exam results, and performance."""

from datetime import datetime
from typing import Optional

from app.database import get_session
from app.deps import require_login
from app.models import (
    Exam,
    ExamAttempt,
    EssayAnswer,
    ExamQuestion,
    MCQResult,
    Student,
    User,
)
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ITEMS_PER_PAGE = 10  # Number of exam results per page


@router.get("/student/grades")
def view_student_grades(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_login),
    sort: Optional[str] = Query("date", regex="^(date|exam|score)$"),
    direction: Optional[str] = Query("desc", regex="^(asc|desc)$"),
    page: Optional[int] = Query(1, ge=1),
):
    """Display all exam results and grades for the current student.

    Features:
    - Shows both essay and MCQ exam results
    - Published vs unpublished exam results
    - Sorting by exam name, date, or score
    - Pagination
    """

    try:
        if current_user.role != "student":
            raise HTTPException(status_code=403, detail="Only students can view their grades")

        # Get student record - try multiple ways to find the student_id
        student_id = getattr(current_user, "student_id", None)
        if student_id is None:
            s = session.exec(select(Student).where(Student.user_id == current_user.id)).first()
            if s:
                student_id = s.id

        if student_id is None:
            raise HTTPException(status_code=404, detail="No linked student record found")

        student = session.get(Student, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student record not found")

        # Collect all exam results (essay + MCQ)
        results = []

        # Get essay attempts with grades
        essay_attempts = session.exec(
            select(ExamAttempt).where(
                (ExamAttempt.student_id == student_id) & (ExamAttempt.status.in_(["submitted", "timed_out"]))
            )
        ).all()

        for attempt in essay_attempts:
            exam = session.get(Exam, attempt.exam_id)
            if not exam:
                continue

            # Get answers for this attempt
            answers = session.exec(select(EssayAnswer).where(EssayAnswer.attempt_id == attempt.id)).all()

            # Calculate total marks awarded
            total_marks = sum((a.marks_awarded or 0) for a in answers)
            total_possible = 0

            # Get total possible marks
            questions = session.exec(select(ExamQuestion).where(ExamQuestion.exam_id == attempt.exam_id)).all()
            total_possible = sum((q.max_marks or 0) for q in questions)

            # Check if graded (any answer has marks_awarded)
            is_graded = any(a.marks_awarded is not None for a in answers)

            results.append(
                {
                    "exam": exam,
                    "type": "Essay",
                    "score": total_marks,
                    "total": total_possible,
                    "percentage": ((total_marks / total_possible * 100) if total_possible > 0 else 0),
                    "submitted_at": attempt.submitted_at or attempt.started_at,
                    "is_published": is_graded,  # Essay is "published" when graded
                    "sort_key": f"{exam.title.lower()}_{attempt.submitted_at or attempt.started_at}",
                }
            )

        # Get MCQ results
        mcq_results = session.exec(select(MCQResult).where(MCQResult.student_id == student_id)).all()

        for mcq_result in mcq_results:
            exam = session.get(Exam, mcq_result.exam_id)
            if not exam:
                continue

            results.append(
                {
                    "exam": exam,
                    "type": "MCQ",
                    "score": mcq_result.score,
                    "total": mcq_result.total_questions,
                    "percentage": (
                        (mcq_result.score / mcq_result.total_questions * 100) if mcq_result.total_questions > 0 else 0
                    ),
                    "submitted_at": mcq_result.graded_at,
                    "is_published": True,  # MCQ results are always published (auto-graded)
                    "sort_key": f"{exam.title.lower()}_{mcq_result.graded_at}",
                }
            )

        # Sort results based on user preference
        if sort == "date":
            results.sort(
                key=lambda x: x["submitted_at"] or datetime.min,
                reverse=(direction == "desc"),
            )
        elif sort == "exam":
            results.sort(key=lambda x: x["exam"].title.lower(), reverse=(direction == "desc"))
        elif sort == "score":
            results.sort(key=lambda x: x["percentage"], reverse=(direction == "desc"))

        # Pagination
        total_results = len(results)
        total_pages = (total_results + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE if total_results > 0 else 1
        page = min(page, total_pages) if total_pages > 0 else 1

        start_idx = (page - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        paginated_results = results[start_idx:end_idx]

        context = {
            "request": request,
            "student": student,
            "results": paginated_results,
            "sort": sort,
            "direction": direction,
            "page": page,
            "current_page": page,
            "total_pages": total_pages,
            "total_results": total_results,
            "items_per_page": ITEMS_PER_PAGE,
            "current_user": current_user,
        }
        return templates.TemplateResponse("student/grades.html", context)
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading grades: {str(e)}")


def calculate_grade(percentage: float) -> str:
    """Convert percentage to letter grade (A/B/C/D/F)."""
    if percentage >= 90:
        return "A"
    elif percentage >= 80:
        return "B"
    elif percentage >= 70:
        return "C"
    elif percentage >= 60:
        return "D"
    else:
        return "F"


@router.get("/grades")
def view_grades(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_login),
):
    """Display published exam results for the current student."""

    try:
        if current_user.role != "student":
            raise HTTPException(status_code=403, detail="Only students can view grades")

        # Get student record
        student_id = getattr(current_user, "student_id", None)
        if student_id is None:
            s = session.exec(select(Student).where(Student.user_id == current_user.id)).first()
            if s:
                student_id = s.id

        if student_id is None:
            raise HTTPException(status_code=404, detail="No linked student record found")

        results = []

        # Get published MCQ results (all MCQ results are published as they're auto-graded)
        mcq_results = session.exec(select(MCQResult).where(MCQResult.student_id == student_id)).all()

        for mcq_result in mcq_results:
            exam = session.get(Exam, mcq_result.exam_id)
            if not exam:
                continue

            percentage = (mcq_result.score / mcq_result.total_questions * 100) if mcq_result.total_questions > 0 else 0
            grade = calculate_grade(percentage)

            results.append(
                {
                    "exam_title": exam.title,
                    "score": mcq_result.score,
                    "total_score": mcq_result.total_questions,
                    "grade": grade,
                    "published_date": (
                        mcq_result.graded_at.strftime("%Y-%m-%d %H:%M") if mcq_result.graded_at else "-"
                    ),
                }
            )

        # Get published essay results (only those that have been graded)
        essay_attempts = session.exec(
            select(ExamAttempt).where(
                (ExamAttempt.student_id == student_id) & (ExamAttempt.status.in_(["submitted", "timed_out"]))
            )
        ).all()

        for attempt in essay_attempts:
            exam = session.get(Exam, attempt.exam_id)
            if not exam:
                continue

            # Get answers for this attempt
            answers = session.exec(select(EssayAnswer).where(EssayAnswer.attempt_id == attempt.id)).all()

            # Check if graded (any answer has marks_awarded set)
            is_graded = any(a.marks_awarded is not None for a in answers)
            if not is_graded:
                continue  # Skip ungraded essays

            total_marks = sum((a.marks_awarded or 0) for a in answers)

            # Get total possible marks
            questions = session.exec(select(ExamQuestion).where(ExamQuestion.exam_id == attempt.exam_id)).all()
            total_possible = sum((q.max_marks or 0) for q in questions)

            percentage = (total_marks / total_possible * 100) if total_possible > 0 else 0
            grade = calculate_grade(percentage)

            results.append(
                {
                    "exam_title": exam.title,
                    "score": total_marks,
                    "total_score": total_possible,
                    "grade": grade,
                    "published_date": (
                        attempt.submitted_at.strftime("%Y-%m-%d %H:%M") if attempt.submitted_at else "-"
                    ),
                }
            )

        context = {
            "request": request,
            "results": results,
            "current_user": current_user,
        }
        return templates.TemplateResponse("view_grades.html", context)

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading grades: {str(e)}")
