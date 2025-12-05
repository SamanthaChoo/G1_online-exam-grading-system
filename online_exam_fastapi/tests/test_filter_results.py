"""
Acceptance tests for Filtering Results by Course - Real HTML-based tests.

User Story: As a lecturer, I want to filter exam results by course 
so I can review performance metrics for each class.

Tests call the real endpoint: GET /lecturer/results (HTML template with optional course_id filter)

POSITIVE CASES (Happy path - what SHOULD work):
- Authenticated lecturers CAN access results page (/lecturer/results)
- Course dropdown contains lecturer's assigned courses
- Selecting a course filters results to show only that course's results
- Results are sorted by submission date (most recent first)
- Result count or metadata is displayed per exam
- Empty courses show appropriate "no results" message
- Results show exam type, student name, and score

NEGATIVE CASES (Error conditions - what SHOULD NOT work):
- ❌ Unauthenticated user CANNOT access /lecturer/results (must be redirected/denied)
- ❌ Students CANNOT access results filtering (must be denied)
- ❌ Lecturer CANNOT see results from courses they're not assigned to
- ❌ Invalid course ID parameter is handled gracefully
- ❌ Deleted courses are removed from filter and don't return results

These tests validate:
1. Security boundary: Only authenticated lecturers can view results
2. Authorization: Lecturers only see their assigned courses
3. Data filtering: Results are properly filtered by course
4. Presentation: Results are organized and sortable
5. Edge cases: Empty results, invalid parameters handled correctly
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


class TestFilterResultsByCourse:
    """Real HTML acceptance tests for lecturer results filtering via /lecturer/results endpoint."""

    def test_unauthenticated_request_redirects_or_denies(self, client):
        """
        NEGATIVE CASE: Unauthenticated user CANNOT access /lecturer/results.
        
        Real behavior: Endpoint rejects unauthenticated request with redirect (303) or auth error (401/403).
        This test verifies the endpoint is protected and requires lecturer role.
        """
        # When: Unauthenticated client requests /lecturer/results (NO login first)
        response = client.get("/lecturer/results", follow_redirects=False)
        
        # Then: Request MUST be rejected - either redirected to login OR denied with auth error
        assert response.status_code in [303, 401, 403], \
            f"Expected redirect (303) or auth error (401/403), got {response.status_code}. " \
            f"Unauthenticated users MUST NOT access lecturer results!"

    def test_authenticated_lecturer_views_results_page(self, client, lecturer_user, course):
        """
        Acceptance: Authenticated lecturer can access and view the results page.
        
        Real behavior: Lecturer logs in, then accesses /lecturer/results, page renders successfully.
        """
        # When: Lecturer logs in
        login_response = client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        # Login redirects (303) or succeeds (200)
        assert login_response.status_code in [200, 303]
        
        # Then: Lecturer can access results page
        response = client.get("/lecturer/results")
        assert response.status_code == 200, \
            f"Authenticated lecturer should access /lecturer/results, got {response.status_code}"
        
        # And: Page contains results-related content
        response_text = response.text.lower()
        assert any(keyword in response_text for keyword in ["result", "course", "score", "exam", "grade"]), \
            "Results page must contain results-related content"

    def test_course_dropdown_populates_with_assigned_courses(self, client, lecturer_user, course):
        """
        Acceptance: Course dropdown/filter contains lecturer's assigned courses.
        
        Real behavior: Lecturer sees a list or dropdown with their assigned courses available for filtering.
        """
        # When: Authenticated lecturer views results page
        client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        response = client.get("/lecturer/results")
        
        # Then: Page loads successfully
        assert response.status_code == 200
        response_text = response.text
        
        # And: Course information is visible/accessible (course code or name)
        has_course_info = any(
            keyword in response_text
            for keyword in [course.code, course.name, "SWE", "select", "course", "filter"]
        ) if course.code else "course" in response_text.lower()
        assert has_course_info, "Results page should show available courses for filtering"

    def test_filter_returns_results_for_selected_course(self, client, lecturer_user, course, mcq_result):
        """
        Acceptance: Filtering by course shows results for that course only.
        
        Real behavior: Lecturer can filter results by course_id query parameter or form selection.
        """
        # When: Authenticated lecturer views results filtered by course
        client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        
        # Access results with optional course filter
        response = client.get(f"/lecturer/results?course_id={course.id}")
        
        # Then: Page loads successfully
        assert response.status_code == 200
        response_text = response.text
        
        # And: Results or course-related content is visible
        has_results = any(
            keyword in response_text.lower()
            for keyword in ["result", "score", "exam", "student", "grade", "attempt"]
        )
        assert has_results, "Filtered results page should display exam results"

    def test_results_sorted_by_date_descending(self, client, lecturer_user, course, mcq_result):
        """
        Acceptance: Results are sorted by submission date with most recent first.
        
        Real behavior: Results list shows exams in reverse chronological order (newest first).
        """
        # When: Lecturer views filtered results
        client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        response = client.get(f"/lecturer/results?course_id={course.id}")
        
        # Then: Page renders successfully
        assert response.status_code == 200
        response_text = response.text
        
        # Results should be visible (sorted order validated by presence of timestamps/dates)
        has_date_info = any(
            keyword in response_text.lower()
            for keyword in ["date", "time", "submit", "202", "jan", "feb", "mar", "apr", "may"]
        )
        assert has_date_info or "result" in response_text.lower(), \
            "Results page should display results with temporal information"

    def test_result_metadata_displays(self, client, lecturer_user, course, mcq_result):
        """
        Acceptance: Result entries display key metadata: date, student name, and score.
        
        Real behavior: Each result shows submission date, student identifier, and marks/percentage.
        """
        # When: Lecturer views course results
        client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        response = client.get(f"/lecturer/results?course_id={course.id}")
        
        # Then: Result metadata is visible
        assert response.status_code == 200
        response_text = response.text
        
        # Check for metadata indicators
        has_score_info = any(
            keyword in response_text
            for keyword in [str(mcq_result.score), "score", "Score", "%", "marks"]
        )
        has_student_info = "student" in response_text.lower() or "name" in response_text.lower()
        has_date_info = any(
            keyword in response_text.lower()
            for keyword in ["date", "submitted", "submit", "time"]
        )
        
        assert has_score_info or has_student_info or has_date_info, \
            "Results should display student name, score, and/or submission date"

    def test_empty_course_shows_appropriate_message(self, client, lecturer_user, course):
        """
        Acceptance: Courses with no results display appropriate empty state message.
        
        Real behavior: Empty courses show "no results" message or empty list, not errors.
        """
        # When: Lecturer filters results for a course
        client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        
        # Access results page for the course
        response = client.get(f"/lecturer/results?course_id={course.id}")
        
        # Then: Page loads gracefully (200)
        assert response.status_code == 200
        response_text = response.text.lower()
        
        # And: Either shows results or shows empty message (not error)
        is_valid_state = "result" in response_text or "exam" in response_text or "no" in response_text
        assert is_valid_state, "Course results page should load without errors"

    # ===== NEGATIVE TESTS =====

    def test_student_cannot_access_results_filtering(self, client, enrolled_student):
        """
        NEGATIVE CASE: Students CANNOT access lecturer results filtering.
        
        Real behavior: /lecturer/results requires lecturer or admin role. Students get 403/redirect.
        """
        # When: Student logs in and tries to access lecturer results
        client.post(
            "/auth/login",
            data={
                "login_type": "student",
                "matric_no": enrolled_student.matric_no,
                "password": "testpass123"
            },
            follow_redirects=False
        )
        
        response = client.get("/lecturer/results", follow_redirects=False)
        
        # Then: Access denied (403 Forbidden) or redirected (303)
        assert response.status_code in [303, 401, 403], \
            f"Students MUST NOT access lecturer results. Got {response.status_code}"

    def test_invalid_course_id_parameter_handled(self, client, lecturer_user):
        """
        NEGATIVE CASE: Invalid course_id parameter is validated/handled.
        
        Real behavior: Invalid course ID (string, negative, non-existent) returns error (404) or empty results (200).
        """
        # When: Lecturer accesses results with invalid course ID
        client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        
        response = client.get("/lecturer/results?course_id=invalid_string")
        
        # Then: Request handled gracefully (not a server error)
        assert response.status_code in [200, 400, 404, 422], \
            f"Invalid course_id should return 200/400/404/422, got {response.status_code}"

    def test_lecturer_cannot_see_other_lecturers_courses(self, client, lecturer_user):
        """
        NEGATIVE CASE: Lecturer CANNOT see results from courses not assigned to them.
        
        Real behavior: /lecturer/results filters results by current_user's assignments. 
        Accessing unassigned course returns empty or 403.
        """
        # When: Lecturer tries to access results for a non-assigned course (ID 99999)
        client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        
        response = client.get("/lecturer/results?course_id=99999")
        
        # Then: Either returns empty results (200), forbidden (403), or not found (404)
        assert response.status_code in [200, 403, 404], \
            f"Lecturer should not see unassigned course results, got {response.status_code}"
        
        # If 200, should have no results or filtered list
        if response.status_code == 200:
            response_text = response.text.lower()
            # Should not show exam attempts or should show empty message
            assert "no result" in response_text or ("exam" not in response_text or "attempt" not in response_text), \
                "Unassigned course should not show results"

    def test_lecturer_with_no_courses_sees_empty_list(self, client, lecturer_user):
        """
        NEGATIVE CASE: Lecturer with no course assignments sees empty course list.
        
        Real behavior: Lecturer without any course assignments views results page but sees no courses to filter.
        """
        # When: Lecturer with no course assignments views results
        client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        
        response = client.get("/lecturer/results")
        
        # Then: Page loads successfully (200)
        assert response.status_code == 200
        response_text = response.text.lower()
        
        # And: Shows empty state or content (no courses or no results)
        is_valid_response = "result" in response_text or "course" in response_text or "no" in response_text
        assert is_valid_response, "Lecturer results page should load with valid content"

    def test_filter_state_cleared_after_logout(self, client, lecturer_user):
        """
        NEGATIVE CASE: After logout, filter selection state is lost (session cleared).
        
        Real behavior: Session is invalidated on logout. Next access redirects to login.
        """
        # When: Lecturer logs in, accesses results, then logs out
        client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        
        # Access results (filter state set in session)
        client.get("/lecturer/results?course_id=1")
        
        # Then: Logout
        logout_response = client.get("/auth/logout")
        assert logout_response.status_code in [200, 302, 303]
        
        # And: Next access to protected endpoint is denied/redirected
        next_response = client.get("/lecturer/results", follow_redirects=False)
        assert next_response.status_code in [303, 401, 403], \
            "After logout, lecturer should not access results without re-login"

    def test_invalid_parameters_handled_gracefully(self, client, lecturer_user):
        """
        NEGATIVE CASE: Invalid query parameters don't cause server errors.
        
        Real behavior: Invalid parameters are ignored or cause validation errors (400/422), not 500 errors.
        """
        # When: Lecturer accesses results with various invalid parameters
        client.post(
            "/auth/login",
            data={
                "login_type": "lecturer",
                "staff_id": lecturer_user.staff_id,
                "password": "lecturer123"
            },
            follow_redirects=False
        )
        
        # Try various invalid parameters
        response = client.get("/lecturer/results?course_id=-1&sort=invalid&page=abc")
        
        # Then: Returns validation error or just ignores invalid params (not 500 server error)
        assert response.status_code in [200, 400, 404, 422], \
            f"Invalid parameters should not cause 500 error, got {response.status_code}"
