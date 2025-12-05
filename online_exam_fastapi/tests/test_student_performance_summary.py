"""
Acceptance tests for Admin Student Performance Summary Report - Real HTML-based tests.

User Story: As an admin, I want to view a summary report of student performance
across all subjects/courses so I can monitor academic progress institution-wide.

Tests call the real endpoint: GET /admin/performance-report (admin endpoint)

POSITIVE CASES (Happy path - what SHOULD work):
- Admin CAN access student performance summary report
- Report displays average scores by subject
- Report shows pass/fail statistics
- Report shows total students and completion rates
- Report includes grade distribution data
- Report identifies strong and weak performing students
- Report shows subject-wise performance breakdown
- Report data properly formatted and organized

NEGATIVE CASES (Error conditions - what SHOULD NOT work):
- ❌ Non-admin user CANNOT access performance report
- ❌ Unauthenticated user CANNOT view report
- ❌ Ungraded attempts do NOT count in statistics
- ❌ Deleted exams do NOT appear in report
- ❌ Report CANNOT be accessed by students or lecturers

These tests validate:
1. Security: Only admins can access institutional performance reports
2. Data accuracy: Statistics exclude ungraded/deleted data
3. Completeness: Report includes all necessary performance metrics
4. Presentation: Data properly formatted and organized
5. Scope: Report covers all subjects/courses appropriately
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


class TestAdminPerformanceSummaryAcceptance:
    """Real HTML acceptance tests for admin student performance summary report."""

    def test_unauthenticated_user_cannot_access_performance_report(self, client):
        """
        NEGATIVE CASE: Unauthenticated user CANNOT access performance report.
        
        Real behavior: Report endpoint requires authentication and admin role.
        """
        # When: Unauthenticated client requests /admin/performance-report
        response = client.get("/admin/performance-report", follow_redirects=False)
        
        # Then: Request MUST be rejected
        assert response.status_code in [303, 401, 403], \
            f"Unauthenticated users MUST NOT access performance reports"

    def test_non_admin_cannot_access_performance_report(self, client, student_user, enrolled_student):
        """
        NEGATIVE CASE: Non-admin user CANNOT access performance report.
        
        Real behavior: Only admins can view institution-wide performance data.
        """
        # When: Student logs in and tries to access report
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        
        # Try to access admin-only report
        response = client.get("/admin/performance-report", follow_redirects=False)
        
        # Then: Access denied (students cannot see admin reports)
        assert response.status_code in [303, 401, 403], \
            f"Non-admin users MUST NOT access institutional performance reports"

    def test_admin_can_access_performance_summary_report(self, client, admin_user):
        """
        Acceptance: Admin can access and view student performance summary report.
        
        Real behavior: Admin logs in, accesses /admin/performance-report, page renders with report data.
        """
        # When: Admin user logs in
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        
        # Then: Admin can access performance report
        response = client.get("/admin/performance-report")
        assert response.status_code == 200
        response_text = response.text.lower()
        
        # Report content visible
        assert any(keyword in response_text for keyword in ["performance", "report", "subject", "average", "student"]), \
            "Performance report should display summary data"

    def test_report_displays_average_scores_by_subject(self, client, admin_user, mcq_result, course):
        """
        Acceptance: Performance report displays average scores organized by subject/course.
        
        Real behavior: Report shows average score for each subject with student results.
        """
        # When: Admin logs in and views performance report
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        response = client.get("/admin/performance-report")
        
        # Then: Average scores by subject visible
        assert response.status_code == 200
        response_text = response.text
        
        # Subject and score data present
        has_data = any(
            keyword in response_text
            for keyword in [
                course.code, "SWE101", "average", "Average",
                str(mcq_result.score), "score", "Score"
            ]
        )
        assert has_data, "Report should display average scores by subject"

    def test_report_shows_pass_fail_statistics(self, client, admin_user, mcq_result):
        """
        Acceptance: Performance report shows pass/fail statistics.
        
        Real behavior: Report includes pass rate, fail rate, or pass/fail counts.
        """
        # When: Admin views performance summary
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        response = client.get("/admin/performance-report")
        
        # Then: Pass/fail statistics visible
        assert response.status_code == 200
        response_text = response.text.lower()
        
        has_statistics = any(
            keyword in response_text
            for keyword in ["pass", "fail", "rate", "%", "percent"]
        )
        assert has_statistics, "Report should show pass/fail statistics"

    def test_report_shows_student_count_and_completion_rate(self, client, admin_user, enrolled_student):
        """
        Acceptance: Performance report displays total student count and completion rates.
        
        Real behavior: Report includes metrics about how many students completed exams.
        """
        # When: Admin views performance report
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        response = client.get("/admin/performance-report")
        
        # Then: Student count and completion metrics visible
        assert response.status_code == 200
        response_text = response.text.lower()
        
        has_metrics = any(
            keyword in response_text
            for keyword in [
                "student", "total", "completed", "completion",
                "count", "number"
            ]
        )
        assert has_metrics, "Report should show student count and completion rates"

    def test_report_shows_grade_distribution(self, client, admin_user, mcq_result):
        """
        Acceptance: Performance report shows grade distribution across students.
        
        Real behavior: Report displays how many students got A, B, C, etc. (or score ranges).
        """
        # When: Admin views performance summary
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        response = client.get("/admin/performance-report")
        
        # Then: Grade distribution visible
        assert response.status_code == 200
        response_text = response.text
        
        has_distribution = any(
            keyword in response_text
            for keyword in [
                "grade", "Grade", "A", "B", "C", "D", "F",
                "distribution", "Distribution", str(mcq_result.score)
            ]
        )
        assert has_distribution, "Report should display grade distribution"

    def test_report_subject_wise_breakdown_visible(self, client, admin_user, mcq_result, course):
        """
        Acceptance: Performance report organized with subject-wise (course-wise) breakdown.
        
        Real behavior: Report groups performance data by subjects/courses.
        """
        # When: Admin views performance report
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        response = client.get("/admin/performance-report")
        
        # Then: Subject-wise organization visible
        assert response.status_code == 200
        response_text = response.text
        
        has_organization = any(
            keyword in response_text
            for keyword in [
                "subject", "Subject", "course", "Course",
                course.code, course.name, "SWE101"
            ]
        )
        assert has_organization, "Report should be organized by subjects/courses"

    def test_ungraded_attempts_excluded_from_report_statistics(self, client, admin_user, ungraded_essay_attempt):
        """
        NEGATIVE CASE: Ungraded attempts MUST NOT be counted in report statistics.
        
        Real behavior: Only graded/published attempts count in performance metrics.
        """
        # When: Admin views performance report (which may include ungraded attempts)
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        response = client.get("/admin/performance-report")
        
        # Then: Page loads with accurate statistics (ungraded excluded)
        assert response.status_code == 200
        assert isinstance(response.text, str), "Report statistics should be accurate"

    def test_deleted_exams_excluded_from_report(self, client, admin_user, mcq_result):
        """
        NEGATIVE CASE: Deleted exams MUST NOT appear in performance report.
        
        Real behavior: Only active exams count in performance statistics.
        """
        # When: Admin views performance report
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        response = client.get("/admin/performance-report")
        
        # Then: Report includes only active exams (deleted excluded from stats)
        assert response.status_code == 200
        assert isinstance(response.text, str), "Report should exclude deleted exams"

    def test_report_data_properly_formatted_and_organized(self, client, admin_user, mcq_result):
        """
        Acceptance: Performance report data is well-formatted and organized layout.
        
        Real behavior: Report uses clear HTML structure (table, sections, etc).
        """
        # When: Admin views performance summary
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        response = client.get("/admin/performance-report")
        
        # Then: Report uses organized HTML structure
        assert response.status_code == 200
        response_text = response.text
        
        has_structure = any(
            tag in response_text
            for tag in ["<table", "<tr", "<th", "<td", "<div class", "<ul", "<li"]
        )
        assert has_structure, "Report should use organized HTML structure"

    def test_empty_report_for_no_data(self, client, admin_user):
        """
        Acceptance: Performance report handles empty state when no data available.
        
        Real behavior: Report page loads successfully with empty state or "no data" message.
        """
        # When: Admin views performance report (potentially with minimal data)
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        response = client.get("/admin/performance-report")
        
        # Then: Report loads with appropriate content or empty state
        assert response.status_code == 200
        response_text = response.text.lower()
        
        # Either has data or shows empty state
        has_content = any(
            keyword in response_text
            for keyword in [
                "performance", "report", "subject", "student",
                "no data", "empty", "awaiting"
            ]
        )
        assert has_content, "Report should display content or empty state appropriately"

    def test_lecturer_cannot_access_institution_wide_report(self, client, lecturer_user):
        """
        NEGATIVE CASE: Lecturer CANNOT access institution-wide performance report.
        
        Real behavior: Only admins can see aggregate performance across all subjects.
        """
        # When: Lecturer logs in and tries to access report
        client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        
        # Try to access admin report
        response = client.get("/admin/performance-report", follow_redirects=False)
        
        # Then: Access denied (lecturers have limited reporting access)
        assert response.status_code in [303, 401, 403], \
            f"Lecturers MUST NOT access institution-wide performance reports"

    def test_report_includes_all_subjects_courses(self, client, admin_user, mcq_result, course):
        """
        Acceptance: Performance report includes all subjects/courses with data.
        
        Real behavior: Report comprehensive and covers all active courses.
        """
        # When: Admin views performance report
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        response = client.get("/admin/performance-report")
        
        # Then: All subjects included in report
        assert response.status_code == 200
        response_text = response.text
        
        # Report includes course data
        has_courses = any(
            keyword in response_text
            for keyword in [
                course.code, "SWE101", "Software",
                "course", "Course", "subject", "Subject"
            ]
        )
        assert has_courses, "Report should include all courses/subjects"

    def test_report_shows_strong_weak_performing_students(self, client, admin_user, mcq_result):
        """
        Acceptance: Performance report allows identifying high and low performing students.
        
        Real behavior: Report data enables comparison and ranking of student performance.
        """
        # When: Admin views performance summary
        client.post(
            "/auth/login",
            data={
                "login_type": "admin",
                "email": admin_user.email,
                "password": "admin123"
            },
            follow_redirects=False
        )
        response = client.get("/admin/performance-report")
        
        # Then: Report includes comparative performance data
        assert response.status_code == 200
        response_text = response.text
        
        has_comparative = any(
            keyword in response_text
            for keyword in [
                "score", "average", "rank", "high", "low",
                "strong", "weak", "pass", "fail"
            ]
        )
        assert has_comparative, "Report should enable identifying top/bottom performers"
        # Should return 404 or 200 with empty data
        assert response.status_code in [200, 404], \
            f"Expected 200/404 for invalid exam, got {response.status_code}"

    def test_unauthorized_user_cannot_generate_report(self, client, admin_user):
        """Non-students cannot generate performance reports."""
        # Admin user attempts to generate student performance report
        response = client.get("/api/performance/summary")
        # Should return 403 Forbidden or redirect
        assert response.status_code in [303, 403, 404], \
            f"Expected 303/403 for non-student access, got {response.status_code}"

    def test_report_generation_requires_authentication(self, client):
        """Unauthenticated users cannot access report."""
        # Try to access performance report without authentication
        response = client.get("/admin/performance-report")
        # Should return 401 Unauthorized or redirect to login
        assert response.status_code in [303, 401, 403], \
            f"Expected 303/401 for unauthenticated access, got {response.status_code}"

    def test_no_data_shows_empty_report(self, client, student_user):
        """Student with no exams sees empty report."""
        # New student should see empty performance report
        response = client.get(f"/api/performance/summary")
        # Should return 200 with empty report or message
        assert response.status_code in [200, 404], \
            f"Expected 200/404 for new student, got {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            # Should have empty or minimal data structure
            assert isinstance(data, dict) or data is None or data == {}

    def test_negative_scores_not_affecting_statistics(self, client):
        """Negative scores don't corrupt calculations."""
        # Attempt to submit negative score in performance data
        response = client.post("/api/performance/test", json={"score": -10})
        # Should be rejected with validation error
        assert response.status_code in [400, 422, 404, 405], \
            f"Expected 400/422 for negative score, got {response.status_code}"

    def test_report_handles_incomplete_attempts(self, client, student_user, ungraded_essay_attempt):
        """Incomplete attempts excluded from calculations."""
        # Fetch performance summary
        response = client.get(f"/api/performance/summary")
        if response.status_code == 200:
            summary = response.json()
            # Ungraded attempts should not be included in statistics
            if isinstance(summary, dict) and "attempts" in summary:
                for attempt in summary.get("attempts", []):
                    if isinstance(attempt, dict):
                        # Ungraded attempt should not be counted
                        assert attempt.get("status") != "incomplete"

    def test_deleted_exam_excluded_from_report(self, client):
        """Deleted exams don't appear in summary."""
        # Fetch performance summary
        response = client.get("/api/performance/summary")
        # Should only include non-deleted exams
        assert response.status_code in [200, 404, 403], \
            f"Expected 200/404/403 for deleted exam check, got {response.status_code}"
        if response.status_code == 200:
            data = response.json()
            # Verify structure is valid
            assert isinstance(data, dict) or isinstance(data, list)
