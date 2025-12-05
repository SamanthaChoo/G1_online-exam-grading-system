# Comprehensive Test Suite - Online Exam Grading System

## Overview
Complete pytest test suite for 6 Sprint 2 user stories with 50+ test cases covering positive and negative scenarios.

---

## Test Infrastructure

### `conftest.py` - Test Configuration
**Purpose**: Central pytest configuration with database setup and shared fixtures

**Key Components**:
- **In-Memory Database**: SQLite `:memory:` for fast, isolated testing
- **Session Scope**: Auto-cleanup between tests via `cleanup_db_between_tests()`
- **Dependency Override**: TestClient overrides FastAPI `get_session` dependency
- **Pytest Hooks**: Custom summary reporting at session end

**Key Fixtures** (8 total):
1. `client` - FastAPI TestClient with test database override
2. `admin_user` - Admin with role="admin"
3. `lecturer_user` - Lecturer with staff_id="L001"
4. `student_user` - Student with matric_no="SWE2001"
5. `course` - SWE101 course with lecturer assignment
6. `enrolled_student` - Student enrolled in course
7. `essay_exam` - 90-min essay exam with 2 questions, marks_awarded support
8. `mcq_exam` - 30-min MCQ exam with 3 questions
9. `graded_essay_attempt` - Submission with marks_awarded=8.5, feedback set
10. `ungraded_essay_attempt` - Submission with marks_awarded=None
11. `mcq_result` - MCQResult with score=24/3 questions

**Database Cleanup Order** (preserves FK constraints):
1. MCQ tables: `mcqanswer`, `mcqresult`, `mcqquestion`
2. Essay tables: `essayanswer`, `examattempt`, `examquestion`
3. Core tables: `exam`, `enrollment`, `courselecturer`, `course`
4. User tables: `student`, `user`, `passwordresettoken`

---

## Test Files

### 1. `test_review_graded_attempt.py` (141 lines)
**User Story**: Read-only grading review for submitted essays

**Database Setup**:
- Uses `graded_essay_attempt` fixture (marks_awarded=8.5)
- Uses `ungraded_essay_attempt` fixture (marks_awarded=None)

#### Positive Tests (5)
1. `test_graded_attempt_displays_read_only_badge()`
   - Verifies `is_graded=True` flag set when marks_awarded present
   - Fixture: `graded_essay_attempt`
   
2. `test_graded_attempt_shows_grader_feedback()`
   - Confirms `grader_feedback` field populated
   - Example: "Good response, but could be more detailed."
   
3. `test_graded_attempt_shows_final_score()`
   - Validates total score display: 8.5 out of 10
   - Uses fixture's marks_awarded value
   
4. `test_graded_attempt_marks_are_float_type()`
   - Confirms float support (8.5, not 8)
   - Validates schema change from int→float
   
5. `test_ungraded_attempt_shows_editable_fields()`
   - Ungraded attempts have editable input fields
   - Save button visible for marks_awarded
   - Uses `ungraded_essay_attempt` fixture

#### Negative Tests (3)
1. `test_modifying_graded_scores_rejected()`
   - Attempt to modify marks_awarded fails
   - Read-only enforcement
   
2. `test_nonexistent_attempt_returns_404()`
   - GET /essay/{exam_id}/grade/{attempt_id} with invalid ID
   - HTTP 404 response
   
3. `test_unauthorized_lecturer_cannot_view_graded_attempt()`
   - Lecturer views another lecturer's course results
   - Access control: 303 or 403
   - Uses another lecturer fixture

---

### 2. `test_filter_results_by_course.py` (195 lines)
**User Story**: Lecturer filters results by assigned course

**Database Setup**:
- Multiple courses with lecturer assignments
- Multiple student enrollments
- Exam results per course

#### Positive Tests (5)
1. `test_filter_returns_results_for_selected_course()`
   - GET /lecturer/results?course_id={id}
   - Returns only exams for selected course
   
2. `test_lecturer_sees_only_assigned_courses()`
   - Lecturer sees course dropdown with only assigned courses
   - Query: `select(CourseLecturer).where(CourseLecturer.lecturer_id == current_user.id)`
   
3. `test_admin_sees_all_courses()`
   - Admin filter shows all courses
   - No CourseLecturer restriction
   
4. `test_results_grouped_by_exam()`
   - Hierarchy: Course → Exam → Student Results
   - Example grouping in template
   
5. `test_course_dropdown_populates_correctly()`
   - Dropdown populated with lecturer's courses
   - Option values match course.id

#### Negative Tests (6)
1. `test_nonexistent_course_returns_empty_results()`
   - Course ID 99999: returns empty results or 404
   
2. `test_unauthorized_lecturer_cannot_view_other_courses()`
   - Lecturer L001 cannot see Lecturer L002's courses
   - 303 redirect or 403 Forbidden
   
3. `test_student_cannot_access_filter_results()`
   - GET /lecturer/results as student
   - 403 Forbidden (non-lecturer role)
   
4. `test_invalid_course_id_parameter()`
   - course_id="abc" (non-numeric)
   - 400 Bad Request or 422 Unprocessable Entity
   
5. `test_no_courses_assigned_lecturer()`
   - New lecturer with no course assignments
   - Dropdown remains empty

---

### 3. `test_view_grades.py` (160 lines)
**User Story**: Students view their exam grades

**Database Setup**:
- Multiple exams (MCQ + Essay) for same course
- Graded and ungraded submissions
- MCQResult and EssayAnswer data

#### Positive Tests (5)
1. `test_student_sees_published_mcq_grades()`
   - MCQ score visible: 24/30 or percentage
   - Uses `mcq_result` fixture
   
2. `test_student_sees_graded_essay_results()`
   - Essay grades shown when marks_awarded set
   - Uses `graded_essay_attempt` fixture
   
3. `test_grades_calculation_accurate()`
   - Score summation verified
   - Example: 8.5 + 9.0 = 17.5/20
   
4. `test_student_sees_both_mcq_and_essay_grades()`
   - Both exam types displayed on same page
   - Separate sections or tabs
   
5. `test_grades_display_by_course()`
   - Grades grouped by course
   - Header: "SWE101 - Introduction to Software Engineering"

#### Negative Tests (5)
1. `test_unpublished_grades_not_visible()`
   - marks_awarded=None exams hidden
   - "Grades coming soon" message
   
2. `test_student_cannot_see_other_students_grades()`
   - Cross-student access denied: 303 or 403
   - Student A cannot see Student B's results
   
3. `test_no_grades_shows_empty_state()`
   - New student: empty grades page
   - "No grades available yet" message
   
4. `test_invalid_student_id_returns_error()`
   - GET /student/grades/99999
   - 400 or 404 error
   
5. `test_grades_access_requires_authentication()`
   - Unauthenticated GET /student/grades
   - 301 or 401 redirect to login

---

### 4. `test_student_performance_summary.py` (180 lines)
**User Story**: Admin generates performance summary reports

**Database Setup**:
- Multiple students with diverse scores
- Varying pass/fail rates (>50% = pass)
- Multiple exams per course

#### Positive Tests (6)
1. `test_report_contains_average_score()`
   - Avg = sum(scores) / count
   - Example: (85 + 92 + 78) / 3 = 85.0
   
2. `test_report_contains_pass_rate()`
   - Pass % = (students with score ≥ 50) / total
   - Example: 12/15 = 80%
   
3. `test_report_contains_student_count()`
   - Total enrolled students: 15
   - Displayed in header
   
4. `test_report_organized_by_subject()`
   - Organization: Subject → Exam → Stats
   - Subject headers with pass/fail breakdown
   
5. `test_report_generation_returns_valid_format()`
   - Dict/JSON structure valid
   - Keys: `avg_score`, `pass_rate`, `student_count`, `data`
   
6. `test_report_includes_all_exams()`
   - All course exams included
   - No exams missing

#### Negative Tests (6)
1. `test_invalid_exam_id_handled_gracefully()`
   - GET /admin/performance-report?exam_id=99999
   - 404 or empty report
   
2. `test_no_data_shows_empty_report()`
   - Course with no enrollments
   - Report: `{"avg_score": 0, "student_count": 0}`
   
3. `test_unauthorized_user_cannot_generate_report()`
   - Lecturer/Student cannot access admin report
   - 403 Forbidden
   
4. `test_negative_scores_not_affecting_statistics()`
   - Score validation: min=0, max=100
   - Invalid scores rejected or clamped
   
5. `test_report_with_incomplete_data()`
   - Some students with grades, others without
   - Report handles partial data gracefully
   
6. `test_report_generation_requires_authentication()`
   - Unauthenticated GET /admin/performance-report
   - 301 or 401 redirect

---

### 5. `test_print_student_performance_report.py` (180 lines)
**User Story**: Admin prints performance summary for documentation

**Database Setup**:
- Performance report data ready
- Print format validation

#### Positive Tests (6)
1. `test_print_button_visible_with_data()`
   - Print button rendered when data exists
   - Conditional: `if report.data: show_button()`
   
2. `test_report_contains_printable_html_format()`
   - HTML includes `@media print` CSS
   - Browser-compatible print styles
   
3. `test_report_includes_all_required_sections()`
   - Header, course info, data table, summary, footer
   - All sections present
   
4. `test_print_preserves_data_integrity()`
   - Data unchanged after print operation
   - Read-only: no writes to DB
   
5. `test_print_button_disabled_without_data()`
   - Print button hidden/disabled when no data
   - `if report: show_button() else: hide_button()`

#### Negative Tests (6)
1. `test_print_with_missing_data_handled_gracefully()`
   - Print request with empty report
   - Error message or empty output, not 500
   
2. `test_unauthorized_user_cannot_print_report()`
   - Lecturer tries to print admin report
   - 303 or 403 Forbidden
   
3. `test_print_without_authentication_fails()`
   - Unauthenticated print request
   - 301 or 401 redirect
   
4. `test_invalid_report_format_parameter()`
   - GET /admin/performance-report/print?format=invalid
   - 400 Bad Request or 422 validation error
   
5. `test_print_with_large_dataset_completes()`
   - 100+ students: performance test
   - No timeout, completes in <5s
   
6. `test_print_browser_compatibility()`
   - Uses standard CSS properties
   - No browser-specific features
   - Works in Chrome, Firefox, Safari

---

### 6. `test_realtime_timer.py` (220 lines)
**User Story**: Student sees countdown timer during exam

**Database Setup**:
- Exam with duration_minutes set
- ExamAttempt tracking start/end times

#### Positive Tests (6)
1. `test_timer_displays_correct_duration()`
   - Timer shows exam duration_minutes (30:00)
   - Format: MM:SS with zero-padding
   
2. `test_timer_counts_down_by_second()`
   - Each second decrements by 1
   - 30 sec elapsed → 2 min remaining
   
3. `test_timer_starts_on_exam_start()`
   - GET /exams/{exam_id}/mcq/start
   - ExamAttempt.started_at recorded
   - Timer begins countdown
   
4. `test_timer_stops_on_exam_submission()`
   - POST /exams/{exam_id}/mcq/submit
   - ExamAttempt.completed_at set
   - Timer frozen at submission time
   
5. `test_timer_shows_time_remaining_in_mm_ss_format()`
   - Format exactly MM:SS (e.g., "25:45")
   - 5-character display
   
6. `test_timer_shows_warning_at_five_minutes()`
   - Red/yellow color when time_remaining ≤ 5:00
   - Visual alert for time management

#### Negative Tests (7)
1. `test_timer_not_started_for_invalid_exam()`
   - GET /exams/99999/mcq/start
   - 404 Not Found, no timer
   
2. `test_timer_shows_zero_for_expired_exam()`
   - Exam duration exceeded: timer shows 00:00
   - Submission enforced
   
3. `test_timer_with_missing_duration_defaults_gracefully()`
   - Exam.duration_minutes = NULL
   - Default to 60 minutes
   
4. `test_timer_persists_through_page_refresh()`
   - F5 refresh: timer resumes from correct time
   - Session state preserved via ExamAttempt.started_at
   
5. `test_timer_not_displayed_for_not_started_exams()`
   - Before clicking "Start Exam"
   - Timer hidden, only "Start Exam" button visible
   
6. `test_timer_access_requires_authentication()`
   - Unauthenticated GET /exams/{exam_id}/mcq/start
   - 301 or 401 redirect to login
   
7. `test_timer_displays_correct_time_after_interruption()`
   - Network delay handling
   - Timer reflects actual elapsed time, not just tick count
   - Example: 25s elapsed on 30min exam → 29:35 remaining

---

## Running the Tests

### Run All Tests
```bash
cd online_exam_fastapi
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_review_graded_attempt.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_filter_results_by_course.py::TestFilterResultsByPositive -v
```

### Run Specific Test
```bash
pytest tests/test_view_grades.py::test_student_sees_published_mcq_grades -v
```

### Run with Coverage
```bash
pytest tests/ --cov=app --cov-report=html
```

### Run with Detailed Output
```bash
pytest tests/ -vv --tb=long
```

---

## Test Execution Output

**Expected Summary** (when all pass):
```
======================================================================
TEST SUMMARY
======================================================================
Total Tests:  50+
Passed:       50+ / 50+
Failed:       0
Errors:       0
======================================================================
```

---

## Test Patterns & Best Practices

### Fixture Pattern
```python
@pytest.fixture
def my_entity():
    with Session(test_engine) as session:
        entity = MyModel(...)
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity
```

### Positive Test Pattern
```python
def test_feature_works_correctly(fixture):
    """Expected behavior: X happens when Y."""
    with Session(test_engine) as session:
        entity = session.get_or_404(MyModel, fixture.id)
        assert entity.field == expected_value
        print("✓ PASS: Feature works as expected")
```

### Negative Test Pattern
```python
def test_feature_rejects_invalid_input():
    """Expected error: X is rejected."""
    with Session(test_engine) as session:
        with pytest.raises(ValueError):
            invalid_op()
        print("✓ PASS (expected failure handled): Invalid input rejected")
```

### Database Cleanup Pattern
- Automatic between tests via `cleanup_db_between_tests()` fixture
- Manual cleanup in reverse FK order
- In-memory database resets quickly (<100ms)

---

## Coverage Map

| Feature | File | Test Count | Coverage |
|---------|------|-----------|----------|
| Read-only Grading | test_review_graded_attempt.py | 8 | ✅ Complete |
| Filter by Course | test_filter_results_by_course.py | 11 | ✅ Complete |
| View Grades | test_view_grades.py | 10 | ✅ Complete |
| Performance Summary | test_student_performance_summary.py | 12 | ✅ Complete |
| Print Report | test_print_student_performance_report.py | 11 | ✅ Complete |
| Realtime Timer | test_realtime_timer.py | 13 | ✅ Complete |
| **TOTAL** | **6 files** | **50+** | **✅ Comprehensive** |

---

## Database Schema Changes Validated

✅ `EssayAnswer.marks_awarded`: `Optional[int]` → `Optional[float]`
- Tests verify float support (8.5, not 8)
- Fixture: `graded_essay_attempt(marks_awarded=8.5)`

✅ `EssayAnswer.grader_feedback`: Added `Optional[str]`
- Tests verify feedback display
- Fixture: `graded_essay_attempt(grader_feedback="...")`

✅ `ExamActivityLog`: Retained for anti-cheating logging
- Not directly tested (infrastructure layer)
- Verified in merge conflicts resolution

---

## Dependencies

**Required Packages** (already in requirements.txt):
- `pytest>=9.0`
- `fastapi`
- `sqlmodel`
- `sqlalchemy`
- `starlette[testclient]`
- `bcrypt` (for password hashing)

**Installation**:
```bash
pip install -r requirements.txt
```

---

## Notes

- **Database**: In-memory SQLite for test isolation and speed
- **Cleanup**: Automatic between tests via pytest fixtures
- **Dependency Override**: TestClient uses test DB, not production DB
- **Print Statements**: Each test prints "✓ PASS:" for manual verification
- **Summary Hook**: Pytest hook prints total/passed/failed at session end
- **No Side Effects**: Tests don't modify production database

---

## Future Enhancements

1. Add parametrized tests for multiple scenarios
2. Add performance tests (timer accuracy, large dataset handling)
3. Add integration tests with live server
4. Add API documentation tests
5. Add security tests (SQL injection, XSS, CSRF)
6. Add load tests for concurrent exam taking

---

**Last Updated**: 2025-12-05
**Status**: ✅ Complete & Ready for Execution
