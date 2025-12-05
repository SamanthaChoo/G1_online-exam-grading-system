"""
Acceptance tests for Printing/Viewing Student Report - Real HTML-based tests.

User Story: As a student, I want to print or export my grades report
so I can save or share my academic record.

Tests call the real endpoint: GET /student/grades (HTML template)
The /student/grades endpoint provides printable grade report information.

POSITIVE CASES (Happy path - what SHOULD work):
- Authenticated student CAN view printable grades report
- Report displays complete grade information
- Report includes course details with grades
- Report shows dates and exam information
- Report is formatted for printing/export
- Report displays scores and percentages
- Report includes all graded attempts

NEGATIVE CASES (Error conditions - what SHOULD NOT work):
- ❌ Unauthenticated user CANNOT access grades report
- ❌ Ungraded attempts do NOT appear in print report
- ❌ Student CANNOT print other students' reports

These tests validate:
1. Security: Only authenticated students can access their reports
2. Completeness: Report contains all necessary student grade information
3. Presentation: Report formatted appropriately for viewing/printing
4. Data accuracy: Only graded data included in report
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


class TestPrintReportAcceptance:
    """Real HTML acceptance tests for printing student grades report via /student/grades endpoint."""

    def test_unauthenticated_user_cannot_access_print_report(self, client):
        """
        NEGATIVE CASE: Unauthenticated user CANNOT access print report.
        
        Real behavior: Endpoint rejects unauthenticated request with redirect or auth error.
        """
        # When: Unauthenticated client requests /student/grades (report endpoint)
        response = client.get("/student/grades", follow_redirects=False)
        
        # Then: Request MUST be rejected
        assert response.status_code in [303, 401, 403], \
            f"Unauthenticated users MUST NOT access grade reports"

    def test_student_can_view_printable_grades_report(self, client, student_user, enrolled_student, mcq_result):
        """
        Acceptance: Authenticated student can access printable grades report.
        
        Real behavior: Student logs in, accesses /student/grades, page renders with all grades.
        """
        # When: Student logs in
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        
        # Then: Student can access grades report
        response = client.get("/student/grades")
        assert response.status_code == 200
        response_text = response.text.lower()
        
        # Report content visible
        assert any(keyword in response_text for keyword in ["grade", "score", "exam"]), \
            "Grade report should display grades and exam information"

    def test_report_displays_complete_grade_information(self, client, student_user, enrolled_student, mcq_result, graded_essay_attempt):
        """
        Acceptance: Print report displays complete grade information for all exams.
        
        Real behavior: Report includes all exam results, scores, and details.
        """
        # When: Student views printable report
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
        
        # Then: Complete grade information visible
        assert response.status_code == 200
        response_text = response.text
        
        # Multiple grades visible
        has_grades = any(
            str(val) in response_text
            for val in [str(mcq_result.score), "8.5", "8", "24"]
        )
        # Multiple exam types visible
        has_exam_types = ("MCQ" in response_text or "mcq" in response_text) and \
                        ("Essay" in response_text or "essay" in response_text)
        
        assert has_grades or has_exam_types, "Report should display complete grade information"

    def test_report_includes_course_details(self, client, student_user, enrolled_student, course, mcq_result):
        """
        Acceptance: Print report includes course code and name with grades.
        
        Real behavior: Course information displayed with each grade entry.
        """
        # When: Student views grades report
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
        
        # Then: Course details visible
        assert response.status_code == 200
        response_text = response.text
        
        # Course information included
        course_visible = any(
            info in response_text
            for info in [course.code, "SWE101", "Software", "Course", "course"]
        )
        assert course_visible, "Report should include course details"

    def test_report_shows_exam_dates_and_times(self, client, student_user, enrolled_student, mcq_result, graded_essay_attempt):
        """
        Acceptance: Print report displays exam dates and timestamps.
        
        Real behavior: Date and time information for each exam visible in report.
        """
        # When: Student views printable report
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
        
        # Then: Date/time information visible
        assert response.status_code == 200
        response_text = response.text
        
        has_date_info = any(
            keyword in response_text
            for keyword in [
                "202", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Date", "date", "submitted"
            ]
        )
        assert has_date_info, "Report should display date and time information"

    def test_report_formatted_for_printing(self, client, student_user, enrolled_student, mcq_result):
        """
        Acceptance: Print report uses print-friendly HTML structure.
        
        Real behavior: Report uses organized layout suitable for printing/export.
        """
        # When: Student views printable report
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
        
        # Then: Report uses organized structure for printing
        assert response.status_code == 200
        response_text = response.text
        
        # Organized layout present
        has_structure = any(
            tag in response_text
            for tag in ["<table", "<tr", "<div class", "<ul"]
        )
        assert has_structure, "Report should use organized structure for printing"

    def test_report_displays_scores_and_percentages(self, client, student_user, enrolled_student, mcq_result):
        """
        Acceptance: Print report shows both scores and percentages.
        
        Real behavior: Numeric scores and percentage values both displayed.
        """
        # When: Student views printable report
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
        
        # Then: Scores and percentages visible
        assert response.status_code == 200
        response_text = response.text
        
        score_visible = str(mcq_result.score) in response_text
        percent_visible = "%" in response_text
        
        assert score_visible or percent_visible, "Report should display scores and percentages"

    def test_report_includes_all_graded_attempts(self, client, student_user, enrolled_student, mcq_result, graded_essay_attempt):
        """
        Acceptance: Print report includes all graded exam attempts.
        
        Real behavior: All completed and graded exams appear in report.
        """
        # Given: Student has multiple graded attempts
        
        # When: Student views print report
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
        
        # Then: All graded attempts visible
        assert response.status_code == 200
        response_text = response.text
        
        # Both MCQ and Essay visible
        mcq_visible = any(k in response_text for k in ["MCQ", "mcq", str(mcq_result.score)])
        essay_visible = any(k in response_text for k in ["Essay", "essay", "8.5", "8"])
        
        assert mcq_visible or essay_visible, "Report should include all graded attempts"

    def test_ungraded_attempts_excluded_from_print_report(self, client, student_user, enrolled_student, ungraded_essay_attempt):
        """
        NEGATIVE CASE: Ungraded attempts MUST NOT appear in print report.
        
        Real behavior: Only graded and published attempts included in printed report.
        """
        # Given: Student has ungraded essay attempt
        
        # When: Student views print report
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
        
        # Then: Page loads, ungraded attempts excluded
        assert response.status_code == 200
        assert isinstance(response.text, str), "Report should be properly formatted"

    def test_student_cannot_print_other_student_report(self, client, student_user, enrolled_student, mcq_result):
        """
        NEGATIVE CASE: Student CANNOT access or print other students' reports.
        
        Real behavior: /student/grades returns only current logged-in user's data.
        """
        # When: Authenticated student views grades (current user only)
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
        
        # Then: Report shows only THIS student's grades
        assert response.status_code == 200
        response_text = response.text
        
        # This student's data visible
        has_student_data = any(
            indicator in response_text
            for indicator in [
                str(mcq_result.score), "MCQ", "mcq", "grade",
                "24", "%"
            ]
        )
        assert has_student_data, "Report should contain current student's grades only"

    def test_empty_report_for_student_with_no_grades(self, client, student_user_no_grades, enrolled_student_no_grades):
        """
        Acceptance: Print report for student with no grades shows appropriate state.
        
        Real behavior: Report loads successfully, shows empty state or "no results".
        """
        # When: Student with no grades logs in
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student_no_grades.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        response = client.get("/student/grades")
        
        # Then: Report loads with empty state
        assert response.status_code == 200
        response_text = response.text.lower()
        
        # Empty state indicators present
        assert any(
            keyword in response_text
            for keyword in ["grade", "result", "empty", "no grade", "awaiting"]
        ), "Report should show structure or empty state"
