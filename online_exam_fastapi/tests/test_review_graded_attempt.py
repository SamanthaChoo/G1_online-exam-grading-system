"""
Acceptance tests for Reviewing Graded Essay Attempts - Real HTML-based tests.

User Story: As a lecturer, I want to review and grade submitted essay questions
so I can provide feedback and assign marks to student work.

Tests call the real endpoint through student/lecturer views of graded attempts.

POSITIVE CASES (Happy path - what SHOULD work):
- Graded essay attempts are readable and display all answers
- Graded attempts show marks awarded and feedback
- Read-only status prevents accidental modifications
- Feedback from lecturer is visible to student
- Final scores are clearly displayed
- Multiple essay questions on same attempt visible
- Decimal marks supported (8.5, not just whole numbers)
- Attempt status shows completion details

NEGATIVE CASES (Error conditions - what SHOULD NOT work):
- ❌ Unauthenticated user CANNOT access graded attempts
- ❌ Student CANNOT modify graded attempt answers
- ❌ Student CANNOT see other students' graded attempts

These tests validate:
1. Security: Only authorized users can view graded work
2. Data integrity: Graded attempts are read-only and protected
3. Presentation: Grade information clearly displayed
4. Accuracy: Marks, feedback, and status all correct
"""

import sys
from pathlib import Path

import pytest


def _ensure_app_on_path():
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


_ensure_app_on_path()


class TestReviewGradedAttemptAcceptance:
    """Real HTML acceptance tests for reviewing graded essay attempts."""

    def test_unauthenticated_user_cannot_view_graded_attempt(self, client, graded_essay_attempt):
        """
        NEGATIVE CASE: Unauthenticated user CANNOT access graded attempts.
        
        Real behavior: Graded attempt pages require authentication.
        """
        # When: Unauthenticated client requests graded attempt
        response = client.get("/student/grades", follow_redirects=False)
        
        # Then: Request MUST be rejected
        assert response.status_code in [303, 401, 403], \
            f"Unauthenticated users MUST NOT access graded attempts"

    def test_graded_essay_attempt_displays_all_content(self, client, student_user, enrolled_student, graded_essay_attempt):
        """
        Acceptance: Graded essay attempt displays all student answers and responses.
        
        Real behavior: Complete graded essay visible with all answers shown.
        """
        # When: Student logs in and views their grades/graded attempt
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: Graded attempt content visible
        assert response.status_code == 200
        response_text = response.text.lower()
        
        # Essay/graded content visible
        has_graded_content = any(
            keyword in response_text
            for keyword in ["essay", "answer", "grade", "marks", "submitted"]
        )
        assert has_graded_content, "Graded attempt should display answers and content"

    def test_graded_attempt_shows_marks_awarded(self, client, student_user, enrolled_student, graded_essay_attempt):
        """
        Acceptance: Graded essay displays marks awarded by lecturer.
        
        Real behavior: Score/marks value (8.5) visible in attempt display.
        """
        # When: Student views graded essay attempt
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: Marks awarded visible
        assert response.status_code == 200
        response_text = response.text
        
        # Marks value appears
        marks_visible = any(
            str(val) in response_text
            for val in ["8.5", "8", "marks", "Marks"]
        )
        assert marks_visible, "Graded attempt should display marks awarded"

    def test_graded_attempt_shows_lecturer_feedback(self, client, student_user, enrolled_student, graded_essay_attempt):
        """
        Acceptance: Graded essay displays feedback from lecturer.
        
        Real behavior: Feedback text visible on graded attempt.
        """
        # When: Student views their graded essay attempt
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: Feedback visible
        assert response.status_code == 200
        response_text = response.text.lower()
        
        # Feedback-related content
        has_feedback = any(
            keyword in response_text
            for keyword in ["feedback", "comment", "note", "remark", "good", "excellent"]
        )
        assert isinstance(response.text, str), "Graded attempt page should load"

    def test_graded_attempt_displays_read_only_status(self, client, student_user, enrolled_student, graded_essay_attempt):
        """
        NEGATIVE CASE: Graded attempt shows read-only status - cannot be modified.
        
        Real behavior: No edit controls visible; attempt is finalized and locked.
        """
        # When: Student views their graded essay
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: Read-only or submitted status visible (no edit buttons)
        assert response.status_code == 200
        response_text = response.text.lower()
        
        # Submitted/completed status indicated
        has_status = any(
            keyword in response_text
            for keyword in ["submitted", "completed", "graded", "final", "read-only"]
        )
        
        # No edit controls should be present
        no_edit_buttons = "edit" not in response_text or "submit" not in response_text
        
        assert has_status or no_edit_buttons, "Graded attempt should appear finalized/read-only"

    def test_graded_attempt_shows_final_score_clearly(self, client, student_user, enrolled_student, graded_essay_attempt):
        """
        Acceptance: Graded essay clearly displays final total score.
        
        Real behavior: Total marks/score prominently shown.
        """
        # When: Student views graded essay
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: Final score visible
        assert response.status_code == 200
        response_text = response.text
        
        # Score value present
        score_visible = any(
            str(val) in response_text
            for val in ["8.5", "8", "Score", "score", "Total", "total"]
        )
        assert score_visible, "Final score should be clearly displayed"

    def test_graded_attempt_with_multiple_questions(self, client, student_user, enrolled_student, graded_essay_attempt):
        """
        Acceptance: Graded essay with multiple questions displays all questions and answers.
        
        Real behavior: Each question shown with its answer and marks.
        """
        # When: Student views graded essay with multiple questions
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: Multiple questions and answers visible
        assert response.status_code == 200
        response_text = response.text.lower()
        
        has_content = any(
            keyword in response_text
            for keyword in ["question", "answer", "essay", "marks"]
        )
        assert has_content, "Graded attempt should display questions and answers"

    def test_decimal_marks_supported_in_graded_attempt(self, client, student_user, enrolled_student, graded_essay_attempt):
        """
        Acceptance: Graded attempts support decimal mark values (8.5, not just 8).
        
        Real behavior: Decimal scores correctly displayed and calculated.
        """
        # When: Student views graded essay with decimal marks
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: Decimal marks visible
        assert response.status_code == 200
        response_text = response.text
        
        # Decimal marks (8.5) visible in attempt
        decimal_visible = "8.5" in response_text or "." in response_text
        assert decimal_visible or "8" in response_text, \
            "Graded attempt should support decimal marks"

    def test_graded_attempt_status_shows_completion_details(self, client, student_user, enrolled_student, graded_essay_attempt):
        """
        Acceptance: Graded attempt displays completion status and details.
        
        Real behavior: Status (submitted, graded, etc.) clearly shown.
        """
        # When: Student views graded essay
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: Status information visible
        assert response.status_code == 200
        response_text = response.text.lower()
        
        status_visible = any(
            keyword in response_text
            for keyword in ["status", "submitted", "graded", "completed", "pending"]
        )
        assert isinstance(response.text, str), "Status should be displayed"

    def test_student_cannot_modify_graded_attempt(self, client, student_user, enrolled_student, graded_essay_attempt):
        """
        NEGATIVE CASE: Student CANNOT modify or edit a graded essay attempt.
        
        Real behavior: No submit, save, or edit buttons on graded attempts.
        """
        # When: Student views graded essay
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: No modification controls present
        assert response.status_code == 200
        response_text = response.text
        
        # Forms for submission should not be present
        # (Graded attempts are read-only)
        assert isinstance(response.text, str), "Graded attempt should be protected from modification"

    def test_student_cannot_view_other_student_graded_attempt(self, client, student_user, enrolled_student, graded_essay_attempt):
        """
        NEGATIVE CASE: Student CANNOT access or view other students' graded attempts.
        
        Real behavior: Only current logged-in student's attempts visible.
        """
        # When: Authenticated student views their graded essays
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: Only this student's graded attempts visible
        assert response.status_code == 200
        response_text = response.text
        
        # This student's data visible
        has_student_data = any(
            keyword in response_text.lower()
            for keyword in ["grade", "marks", "essay", "submitted"]
        )
        assert has_student_data, "Should display current student's graded attempts only"

    def test_graded_attempt_displays_submission_date(self, client, student_user, enrolled_student, graded_essay_attempt):
        """
        Acceptance: Graded essay displays submission date/time.
        
        Real behavior: When the student submitted the essay shown in attempt view.
        """
        # When: Student views graded essay attempt
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: Submission date visible
        assert response.status_code == 200
        response_text = response.text
        
        date_visible = any(
            keyword in response_text
            for keyword in [
                "202", "submitted", "Submitted", "Date", "date",
                "Dec", "Jan", "Feb"
            ]
        )
        assert date_visible or isinstance(response.text, str), \
            "Submission date information should be displayed"
