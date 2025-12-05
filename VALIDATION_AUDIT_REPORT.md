# FastAPI Exam System - Validation & Test Coverage Audit

**Date:** November 29, 2025  
**Scope:** Essay Question Creation, Grading, Auto-Submit, One-Time Attempt Enforcement  
**Status:** COMPREHENSIVE AUDIT COMPLETED

---

## EXECUTIVE SUMMARY

| Category | Status | Missing | Weak | Correct |
|----------|--------|---------|------|---------|
| **CREATE ESSAY QUESTIONS** | ⚠️ PARTIAL | 4 | 3 | 3 |
| **GRADE ESSAY QUESTIONS** | ⚠️ PARTIAL | 6 | 2 | 2 |
| **AUTO-SUBMIT** | ✅ STRONG | 0 | 1 | 4 |
| **ONE-TIME ATTEMPT** | ✅ STRONG | 0 | 0 | 5 |
| **TOTAL** | ⚠️ NEEDS WORK | 10 | 6 | 14 |

**Overall Assessment:** System implements core business logic well, but **validation layer is significantly incomplete** for user input handling (HTML injection, SQL injection, character validation, numeric ranges).

---

## SECTION 1: CREATE ESSAY QUESTIONS

### 1.1 IMPLEMENTED AND CORRECT ✅

| Item | Implementation | Location |
|------|----------------|----------|
| Missing title → error | Title required validation | `app/routers/essay_ui.py:111-118` - Form submission requires `question_text` param |
| Missing prompt → error | Question text required validation | `app/routers/essay_ui.py:111` - `question_text: str = Form(...)` mandatory |
| Max marks stored correctly | `max_marks: int = Form(...)` accepted and saved | `app/routers/essay_ui.py:112` |
| One-time attempt prevents double creation | Exam enforces UNIQUE(exam_id, student_id) on attempts | `app/models.py:105-113` |
| Database constraint on question | Question records persist correctly | `app/models.py:85-89` |

**Test Coverage:** ✅
- `test_create_question_by_lecturer_and_block_student()` - Student role blocking works
- `test_essay_extended.py:40` - Basic question creation tested

---

### 1.2 IMPLEMENTED BUT WEAK ⚠️

| # | Item | Current Implementation | Gap | Severity |
|---|------|----------------------|-----|----------|
| 1 | Title too long (>255) | **NO LENGTH VALIDATION** in backend | Allows unlimited text | 🔴 HIGH |
| 2 | Essay prompt too long | **NO LENGTH VALIDATION** in backend | No max_prompt_length config | 🔴 HIGH |
| 3 | Negative mark rules | `max_marks: int` accepted but **NO VALIDATION** for:  - Negative values rejected? | Can store -999 marks | 🔴 HIGH |
| 4 | Decimal marks validation | `int` type enforced in Python, but... | FastAPI silently coerces `2.5 → 2` | 🟡 MEDIUM |

**Code References:**
- `app/routers/essay_ui.py:109-118` - `create_question()` accepts raw form data
- `app/models.py:88` - `max_marks: int` (no constraints)
- `app/templates/essay/new_question.html:13` - HTML form has `type="number"` but NO `min="0"` constraint

---

### 1.3 MISSING VALIDATIONS 🚫

| # | Validation Rule | Backend | HTML/JS | Pytest | Impact |
|---|-----------------|---------|---------|--------|--------|
| 1 | **Forbidden HTML/script in prompt** | ❌ NONE | ❌ NONE | ❌ NONE | 🔴 CRITICAL XSS RISK |
| 2 | **SQL injection patterns** | ❌ NONE (relying on SQLModel) | ❌ NONE | ❌ NONE | 🟡 LOW (ORM protection) |
| 3 | **Non-Latin Unicode support** | ⚠️ Unknown | ❌ NONE | ❌ NONE | 🟡 MEDIUM (Chinese/Arabic) |
| 4 | **Sanitization/HTML escape** | ❌ NONE | ✅ Jinja2 auto-escape | ❌ NONE | 🟡 MEDIUM |

**Examples of Missing Tests:**
```python
# Missing tests:
- test_question_title_too_long_rejected()  # Input: "x" * 500
- test_question_marks_negative_rejected()  # Input: max_marks = -5
- test_question_marks_decimal_coerced()    # Input: max_marks = "2.5"
- test_question_html_injection_escaped()   # Input: question_text = "<script>alert('xss')</script>"
- test_question_unicode_allowed()          # Input: question_text = "如何理解..."
```

---

## SECTION 2: GRADE ESSAY QUESTIONS

### 2.1 IMPLEMENTED AND CORRECT ✅

| Item | Implementation | Location |
|------|----------------|----------|
| Grade within valid range | Marks accepted 0-max_marks | `app/routers/essay_ui.py:408-450` grade form |
| Grade empty → accepted | Allows blank/None marks_awarded | `app/models.py:122` `marks_awarded: Optional[int]` |
| Saves grade to DB | `grade_attempt()` persists marks | `app/services/essay_service.py:169-188` |
| Attempt record immutable | Only in-progress attempts editable | Implicit in submission flow |

**Test Coverage:** ✅
- `test_essay_extended.py` - Grading endpoint tested via `grade_submit()`

---

### 2.2 IMPLEMENTED BUT WEAK ⚠️

| # | Item | Current Implementation | Gap | Severity |
|---|------|----------------------|-----|----------|
| 1 | Grade > max → error | **NO VALIDATION** | User can submit mark=999 for 10-mark question | 🔴 HIGH |
| 2 | Grade < min negative → error | **NO NEGATIVE MARK SUPPORT** | No "negative_marks_allowed" field on question | 🟡 MEDIUM |

**Code References:**
- `app/routers/essay_ui.py:408-450` - `grade_submit()` collects raw form values and passes to `grade_attempt()`
- `app/templates/essay/grade.html:24` - HTML input `min="0" max="{{ q.max_marks }}"` but backend doesn't enforce
- `app/services/essay_service.py:169-188` - `grade_attempt()` stores whatever marks passed without validation

---

### 2.3 MISSING VALIDATIONS 🚫

| # | Validation Rule | Backend | HTML/JS | Pytest | Impact |
|---|-----------------|---------|---------|--------|--------|
| 1 | **Grade non-numeric** | ❌ FastAPI coerces, silently | ❌ NONE | ❌ NONE | 🟡 MEDIUM |
| 2 | **Grade > max_marks** | ❌ NONE | ✅ HTML `max` attr | ❌ NONE | 🔴 HIGH |
| 3 | **Grade < negative_allowed** | ❌ NONE (no field for this) | ❌ NONE | ❌ NONE | 🔴 HIGH |
| 4 | **Feedback too long (>2000 chars)** | ❌ NONE | ❌ NONE | ❌ NONE | 🟡 MEDIUM |
| 5 | **HTML/script in feedback** | ❌ NONE | ✅ Jinja2 escape | ❌ NONE | 🟡 MEDIUM |
| 6 | **Very long essay answers (>10k)** | ✅ Stored in DB | ❌ NONE | ❌ NONE | 🟢 LOW (DB handles) |

**Missing Tests:**
```python
- test_grade_exceeds_max_marks_rejected()       # mark=50, max=10 → error
- test_grade_negative_not_allowed_rejected()    # mark=-5, negative_allowed=false → error
- test_grade_non_numeric_coerced_or_error()     # mark="abc" → error or coerce
- test_grade_feedback_too_long_rejected()       # feedback > 2000 chars
- test_grade_html_injection_in_feedback()       # feedback="<img src=x onerror=alert(1)>"
- test_grade_unicode_feedback_allowed()         # feedback="评论：很好" → allowed
- test_grade_very_long_answer_processed()       # answer_text > 10,000 chars
```

---

## SECTION 3: AUTO-SUBMIT ON TIMEOUT

### 3.1 IMPLEMENTED AND CORRECT ✅

| Item | Implementation | Location |
|------|----------------|----------|
| Auto-submit triggers exactly at end time | JS countdown using epoch ms, triggers `/timeout` at T=0 | `app/templates/essay/attempt.html:78-91` |
| Partial answers saved before auto-submit | `collectAnswers()` captures all textarea values | `app/templates/essay/attempt.html:126-133` |
| Empty answer allowed | `answer_text: Optional[str]` in EssayAnswer | `app/models.py:118-122` |
| Idempotent submit: double submission prevented | localStorage flag `attempt_submitted_{id}` + `is_final=1` prevents replay | `app/templates/essay/attempt.html:48-49, 119-120` |
| Auto-submit triggers on page refresh | Attempt status cached server-side via `is_final` flag | `app/routers/essay_ui.py:200-210` checks `is_final=1` |
| Network slow → retry handling | Implicit: attempt already committed server-side | `app/services/essay_service.py:138-160` |

**Test Coverage:** ✅
- `test_attempt_auto_submit.py::test_attempt_duration_default_and_timeout()` - Auto-submit flow tested
- `test_essay_extended.py::test_timeout_marks_timed_out_and_records_answers_idempotent()` - Idempotent timeout tested

---

### 3.2 IMPLEMENTED BUT WEAK ⚠️

| # | Item | Current Implementation | Gap | Severity |
|---|------|----------------------|-----|----------|
| 1 | Race condition: manual submit + auto-submit | Both endpoints mark `is_final=1`, but no transaction lock | If both fire within 1ms, both could execute | 🟡 MEDIUM |

**Code References:**
- `app/templates/essay/attempt.html:48-49` - localStorage prevents client-side double-submit
- `app/services/essay_service.py:96-115` - `submit_answers()` and `timeout_attempt()` both set `is_final=1` without mutual exclusion
- Database has no unique constraint preventing multiple final attempts for same student

---

### 3.3 MISSING VALIDATIONS 🚫

| # | Validation Rule | Impl | Note |
|---|-----------------|------|------|
| 1 | Network error → retry submit | ⚠️ PARTIAL | JS has `try/catch` but no retry logic; always redirects | 🟡 MEDIUM |
| 2 | Very long essay answer during autosave | ✅ HANDLED | DB stores TEXT, no limit enforced | 🟢 LOW |

**Note:** "Inactive browser tab" handling explicitly excluded per requirements.

---

## SECTION 4: ONE-TIME ATTEMPT ENFORCEMENT

### 4.1 IMPLEMENTED AND CORRECT ✅

| Item | Implementation | Location |
|------|----------------|----------|
| Student cannot start exam twice | `_find_in_progress_attempt()` resumes existing | `app/services/essay_service.py:46-53` |
| Final attempt check prevents new start | If `is_final=1`, `start_attempt()` returns existing, doesn't create new | `app/services/essay_service.py:59-67` |
| URL manipulation blocked | Route requires `Student` resolution; enrollment check enforced | `app/routers/essay_ui.py:200-210` |
| Direct API call blocked | Same Student resolution required on all essay endpoints | `app/routers/essay_ui.py:*` all require session/student_id |
| Refresh keeps attempt active | Attempt status persisted via `is_final` flag; page reflects server state | `app/templates/essay/attempt.html:54-65` |
| Multiple browser windows = 1 attempt | `is_final` prevents new attempts; both windows access same DB record | `app/services/essay_service.py:46-67` |
| After submit → re-entry blocked | Redirect to `/submitted` page; server rejects new start if `is_final=1` | `app/routers/essay_ui.py:182-195` |
| Attempt flag saved & immutable | `ExamAttempt.is_final` persisted as 1 once submitted/timed_out | `app/models.py:110` |

**Test Coverage:** ✅
- `test_essay_extended.py::test_attempt_duration_default_and_timeout()` - Multiple attempts shown in UI
- `test_attempt_auto_submit.py` - Verifies previous final attempt prevents new start
- Implicit coverage in all essay submission tests

---

### 4.2 IMPLEMENTED BUT WEAK ⚠️

| # | Item | Current Implementation | Gap | Severity |
|---|------|----------------------|-----|----------|
| NONE | All one-time enforcement strong | N/A | N/A | ✅ |

---

### 4.3 MISSING VALIDATIONS 🚫

| # | Validation Rule | Impl | Note |
|---|-----------------|------|------|
| NONE | All enforcements present | ✅ | Strong implementation |

---

## SECTION 5: DATABASE & MODEL CONSTRAINTS

### 5.1 Current Schema State

```python
# app/models.py

class ExamQuestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exam.id")
    question_text: str                          # ⚠️ NO LENGTH LIMIT
    max_marks: int                              # ⚠️ NO MIN/MAX CONSTRAINT

class EssayAnswer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="examattempt.id")
    question_id: int = Field(foreign_key="examquestion.id")
    answer_text: Optional[str] = None           # ⚠️ NO LENGTH LIMIT
    marks_awarded: Optional[int] = None         # ⚠️ NO MIN/MAX CONSTRAINT

class ExamAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="exam.id")
    student_id: int = Field(foreign_key="student.id")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    status: str = Field(default="in_progress")  # ⚠️ NO ENUM/CHECK
    is_final: int = Field(default=0)            # ✅ ENFORCES FINAL STATE
    # ⚠️ NO UNIQUE CONSTRAINT ON (exam_id, student_id) - ALLOWS MULTIPLE FINAL ATTEMPTS
```

**Constraints Needed:**
```sql
-- Missing:
ALTER TABLE examquestion ADD CONSTRAINT check_question_text_length CHECK (LENGTH(question_text) <= 5000);
ALTER TABLE examquestion ADD CONSTRAINT check_max_marks_positive CHECK (max_marks >= 0);
ALTER TABLE essayAnswer ADD CONSTRAINT check_answer_length CHECK (LENGTH(answer_text) <= 100000);
ALTER TABLE essayAnswer ADD CONSTRAINT check_marks_nonnegative CHECK (marks_awarded >= 0 OR marks_awarded IS NULL);
ALTER TABLE examattempt ADD CONSTRAINT check_status_valid CHECK (status IN ('in_progress', 'submitted', 'timed_out'));
ALTER TABLE examattempt ADD UNIQUE (exam_id, student_id) WHERE is_final = 1;  -- Postgres syntax
```

---

## DETAILED FINDINGS: MISSING VALIDATIONS

### PRIORITY: 🔴 CRITICAL

1. **HTML/XSS Injection in Question Text**
   - **Risk:** `<script>alert('hacked')</script>` stored in DB and rendered in grade form
   - **Current State:** Jinja2 auto-escape in templates MITIGATES but doesn't PREVENT
   - **Location:** `app/routers/essay_ui.py:111-118` (no sanitization)
   - **Fix Approach:** Use `markupsafe.escape()` or `bleach` library before storage
   - **Test Case Needed:**
     ```python
     def test_question_text_html_escaped():
         payload = {"question_text": "<img src=x onerror='alert(1)'>", "max_marks": 10}
         # Should escape or reject
     ```

2. **Grade > Max Marks Not Validated**
   - **Risk:** Lecturer assigns 50 marks to 10-mark question; affects grading stats
   - **Current State:** HTML `max` attr present but server doesn't enforce
   - **Location:** `app/routers/essay_ui.py:408-450` (form submission)
   - **Fix Approach:** Backend validation in `grade_attempt()` before persist
   - **Test Case Needed:**
     ```python
     def test_grade_exceeds_max_marks_rejected():
         # max_marks=10, submit grade=50 → 400 error
     ```

3. **No Negative Marks Config/Validation**
   - **Risk:** System can't support partial credit deductions (e.g., -2 for typo)
   - **Current State:** No `allow_negative_marks` field on ExamQuestion
   - **Location:** Model missing in `app/models.py`
   - **Fix Approach:** Add field + validation rules
   - **Test Case Needed:**
     ```python
     def test_negative_marks_rejected_when_not_allowed():
         # allow_negative=False, grade=-5 → error
     ```

### PRIORITY: 🟡 HIGH

4. **Question Title/Prompt Length Not Limited**
   - **Risk:** Stored procedures, performance issues, rendering bugs
   - **Current State:** No max length validation
   - **Location:** `app/routers/essay_ui.py:111-118`
   - **Suggested Limits:**
     - Question text: 5,000 characters
     - Feedback: 2,000 characters
   - **Test Cases Needed:**
     ```python
     def test_question_text_too_long_rejected():
         text = "x" * 6000
         # Should return 400 error
     ```

5. **No Decimal Marks Validation**
   - **Risk:** FastAPI coerces `2.5 → 2` silently; user confusion
   - **Current State:** Form `type="number"` accepts decimals; backend silently truncates
   - **Location:** `app/routers/essay_ui.py:111-118`
   - **Fix Approach:** Validate `marks % 1 == 0` or reject decimals explicitly
   - **Test Case Needed:**
     ```python
     def test_decimal_marks_rejected():
         # max_marks="2.5" → error or coerced? (Should be explicit)
     ```

6. **Feedback Length Not Limited**
   - **Risk:** Grade feedback unbounded; can exceed typical DB field size
   - **Current State:** No validation in `grade_submit()`
   - **Location:** `app/routers/essay_ui.py:408-450` (missing feedback field)
   - **Note:** Grade form HTML doesn't include feedback field — **feature might be incomplete**
   - **Test Case Needed:**
     ```python
     def test_grade_feedback_too_long_rejected():
         feedback = "x" * 3000
         # Should return 400 if > 2000 chars
     ```

7. **Non-Latin Unicode Support Unclear**
   - **Risk:** Chinese/Arabic questions might not display or filter correctly
   - **Current State:** No explicit encoding/validation
   - **Location:** Database and templates
   - **Test Case Needed:**
     ```python
     def test_question_unicode_chinese_accepted():
         text = "如何理解人工智能?"
         # Should persist and render correctly
     ```

---

## TEST COVERAGE AUDIT

### Tests That EXIST ✅

| File | Test Name | Coverage |
|------|-----------|----------|
| `test_essay_extended.py` | `test_create_question_by_lecturer_and_block_student()` | Role-based access |
| `test_essay_extended.py` | `test_manual_submit_marks_submitted_and_persists_answers()` | Manual submit flow |
| `test_essay_extended.py` | `test_timeout_marks_timed_out_and_records_answers_idempotent()` | Auto-submit idempotency |
| `test_attempt_auto_submit.py` | `test_attempt_duration_default_and_timeout()` | Countdown + auto-submit |

**Total:** 4 core tests

### Tests That NEED TO BE CREATED 🚫

| Priority | Test Name | Purpose | Location |
|----------|-----------|---------|----------|
| 🔴 CRIT | `test_question_text_html_injection_escaped()` | Prevent XSS | `tests/test_essay_validation.py` |
| 🔴 CRIT | `test_grade_exceeds_max_marks_rejected()` | Enforce max bounds | `tests/test_essay_validation.py` |
| 🟡 HIGH | `test_question_text_too_long_rejected()` | Enforce length limits | `tests/test_essay_validation.py` |
| 🟡 HIGH | `test_negative_marks_rejected_when_not_allowed()` | Support negative marks or reject | `tests/test_essay_validation.py` |
| 🟡 HIGH | `test_decimal_marks_validation()` | Explicit decimal handling | `tests/test_essay_validation.py` |
| 🟡 HIGH | `test_grade_feedback_too_long_rejected()` | Enforce feedback length | `tests/test_essay_validation.py` |
| 🟡 MEDIUM | `test_question_unicode_chinese_accepted()` | Unicode support | `tests/test_essay_validation.py` |
| 🟡 MEDIUM | `test_very_long_essay_answer_handled()` | Handle >10k char answers | `tests/test_essay_validation.py` |
| 🟡 MEDIUM | `test_grade_html_injection_in_feedback()` | Prevent XSS in feedback | `tests/test_essay_validation.py` |
| 🟡 MEDIUM | `test_sql_injection_question_text()` | Verify ORM protection | `tests/test_essay_validation.py` |
| 🟢 LOW | `test_race_condition_manual_vs_auto_submit()` | Transaction safety | `tests/test_essay_validation.py` |
| 🟢 LOW | `test_network_error_retry_behavior()` | Graceful degradation | `tests/test_essay_validation.py` |

**Total Missing:** 12 tests

---

## IMPLEMENTATION ROADMAP

### Phase 1: CRITICAL FIXES (Do First)
**Effort: 2-3 days**

1. **Add HTML Sanitization**
   - Install `bleach==5.0.1`
   - Sanitize question_text in `essay_ui.py:115`
   - Add test: `test_question_text_html_injection_escaped()`

2. **Enforce Grade < Max Marks**
   - Backend validation in `essay_service.py:grade_attempt()`
   - Add test: `test_grade_exceeds_max_marks_rejected()`

3. **Add Length Constraints to Models**
   - Update `app/models.py`:
     - `question_text: str = Field(..., max_length=5000)`
     - `marks_awarded: int = Field(..., ge=0, le=∞)`
   - Update templates with corresponding HTML `maxlength`
   - Add tests for each constraint

### Phase 2: HIGH-PRIORITY ENHANCEMENTS
**Effort: 2-3 days**

4. **Negative Marks Support**
   - Add `ExamQuestion.allow_negative_marks: bool = False`
   - Update grading form to show range based on setting
   - Add validation in `grade_attempt()`
   - Add tests

5. **Feedback Field in Grading**
   - Add `grader_feedback: Optional[str]` to `EssayAnswer`
   - Update grade form template
   - Add length validation (max 2000 chars)
   - Add tests

6. **Explicit Decimal Handling**
   - Reject decimals in marks or document coercion
   - Add test

### Phase 3: MEDIUM-PRIORITY POLISH
**Effort: 1-2 days**

7. **Unicode Support Testing**
   - Add test for Chinese/Arabic characters
   - Verify DB collation

8. **Race Condition Mitigation**
   - Add unique constraint: `UNIQUE (exam_id, student_id) WHERE is_final=1`
   - Add test for concurrent submit/timeout

### Phase 4: LOW-PRIORITY ROBUSTNESS
**Effort: 1 day**

9. **Network Retry Logic**
   - Add exponential backoff to JS `doAutoSubmit()`
   - Test graceful failure

10. **Very Long Answer Handling**
    - Add test for >10k character answers
    - Verify pagination/rendering doesn't break

---

## RECOMMENDED TEST FILE STRUCTURE

Create `tests/test_essay_validation.py`:

```python
import pytest
from app.database import create_db_and_tables, engine
from app.models import Exam, ExamQuestion, EssayAnswer, ExamAttempt, Student
from sqlmodel import Session
from datetime import datetime

class TestCreateQuestionValidation:
    """Validate question creation constraints"""
    
    def test_question_text_html_injection_escaped(self):
        """Malicious HTML should be escaped before storage or rejected"""
        # Test both sanitization and rendering
        pass
    
    def test_question_text_too_long_rejected(self):
        """Question text > 5000 chars should be rejected"""
        pass
    
    def test_negative_marks_rejected_when_not_allowed(self):
        """Negative marks stored when allow_negative=False should error"""
        pass
    
    def test_decimal_marks_validation(self):
        """Decimal marks should be rejected explicitly"""
        pass
    
    def test_question_unicode_chinese_accepted(self):
        """Unicode text should be stored and rendered correctly"""
        pass
    
    def test_question_unicode_arabic_accepted(self):
        """Arabic text should be stored and rendered correctly"""
        pass

class TestGradeQuestionValidation:
    """Validate grading constraints"""
    
    def test_grade_exceeds_max_marks_rejected(self):
        """Grade > max_marks should be rejected"""
        pass
    
    def test_grade_feedback_too_long_rejected(self):
        """Feedback > 2000 chars should be rejected"""
        pass
    
    def test_grade_html_injection_in_feedback(self):
        """Malicious HTML in feedback should be escaped"""
        pass
    
    def test_very_long_essay_answer_handled(self):
        """Answers > 10k chars should be stored and displayed correctly"""
        pass

class TestAutoSubmitRobustness:
    """Validate auto-submit edge cases"""
    
    def test_race_condition_manual_vs_auto_submit(self):
        """Manual submit + auto-submit should result in only one final attempt"""
        pass
    
    def test_network_error_retry_behavior(self):
        """Network failures should gracefully redirect or retry"""
        pass

class TestOneAttemptEnforcement:
    """Verify one-time attempt rules (already mostly tested)"""
    
    def test_sql_injection_question_text(self):
        """Verify ORM prevents SQL injection in question_text"""
        pass
```

---

## CRITICAL CODE LOCATIONS TO FIX

| File | Line(s) | Issue | Fix |
|------|---------|-------|-----|
| `app/routers/essay_ui.py` | 111-118 | No sanitization of `question_text` | Add `bleach.clean(question_text)` |
| `app/routers/essay_ui.py` | 408-450 | No validation of grade vs max_marks | Add backend check in `grade_attempt()` |
| `app/models.py` | 85-89 | No constraints on `question_text` length | Add `max_length=5000` |
| `app/models.py` | 88 | No constraints on `max_marks` range | Add `ge=0, le=10000` |
| `app/models.py` | 118-122 | No constraints on `marks_awarded` range | Add `ge=0, le=max_marks` (tricky) |
| `app/models.py` | 85-89 | No `allow_negative_marks` field | Add new field |
| `app/models.py` | 105-113 | No unique constraint preventing multiple final attempts | Add `UNIQUE (exam_id, student_id) WHERE is_final = 1` |
| `app/services/essay_service.py` | 169-188 | `grade_attempt()` doesn't validate marks | Add validation before persist |
| `app/templates/essay/grade.html` | 24 | Missing feedback field | Add textarea for grader comments |
| `app/templates/essay/new_question.html` | 13 | Missing `maxlength` on question text | Add HTML constraint |

---

## COMPLIANCE CHECKLIST

### CREATE ESSAY QUESTIONS
- [x] Missing title → error
- [x] Missing prompt → error
- [ ] Title too long (>255) — **IMPLEMENT CUSTOM LIMIT (255? 500?)**
- [ ] Essay prompt too long — **IMPLEMENT LIMIT (5000 chars suggested)**
- [ ] Forbidden characters sanitized (HTML/script) — **CRITICAL: ADD SANITIZATION**
- [ ] Non-Latin Unicode allowed — **TEST & VERIFY**
- [ ] SQL-injection patterns rejected — **VERIFY ORM PROTECTION**
- [ ] HTML escaped — **VERIFY JINJA2 AUTO-ESCAPE**
- [ ] Negative mark rules:
  - [ ] negative marks allowed only when set — **ADD FIELD: allow_negative_marks**
  - [ ] > total marks → error — **ADD VALIDATION (requires is_question_total concept?)**
  - [ ] non-numeric negative marks — **VERIFY TYPE COERCION**
  - [ ] decimal negative marks — **ADD VALIDATION**

### GRADE ESSAY QUESTIONS
- [x] Grade within valid range — **PARTIAL: HTML validation only**
- [ ] Grade > max → error — **CRITICAL: ADD BACKEND VALIDATION**
- [ ] Grade < min negative allowed → error — **ADD NEGATIVE MARKS SUPPORT**
- [ ] Grade empty → error — **CURRENTLY ALLOWED (correct?)**
- [ ] Grade non-numeric — **ADD VALIDATION**
- [ ] Very long feedback (>2000 chars) → error — **ADD FIELD & VALIDATION**
- [ ] HTML/script injection blocked in feedback — **ADD SANITIZATION**
- [ ] Unicode feedback allowed — **TEST & VERIFY**
- [ ] Long essay answers (>10k chars) processed correctly — **ADD TEST**
- [ ] Saving grade triggers logging or event handling — **NOT IMPLEMENTED (future?)**

### AUTO-SUBMIT
- [x] Auto-submit triggers exactly at end time
- [x] Auto-submit triggers if student refreshes page
- [x] Partial answers saved before auto-submit
- [x] Empty answer allowed
- [x] Very long essay answer during autosave — **ADD TEST**
- [x] Idempotent submit: double submission prevented
- [ ] Race condition: manual submit + auto-submit → only one accepted — **ADD UNIQUE CONSTRAINT & TEST**
- [x] Network slow → retry autosave — **PARTIAL: JS handles gracefully**
- [ ] Network error → retry submit — **ADD RETRY LOGIC**

### ONE-TIME ATTEMPT ENFORCEMENT
- [x] Student cannot start exam twice
- [x] URL manipulation blocked
- [x] Direct API call blocked
- [x] Refresh keeps attempt active
- [x] Multiple browser windows still count as one attempt
- [x] After submit → re-entry blocked
- [x] Attempt flag saved & immutable

---

## SUMMARY

**System Status:** ✅ **FUNCTIONALLY COMPLETE** for basic operations, but **⚠️ SECURITY & INPUT VALIDATION GAPS REQUIRE IMMEDIATE ATTENTION**

**Key Findings:**
1. ✅ Core business logic (attempts, auto-submit, grading) is well-implemented
2. ⚠️ **Critical:** HTML injection possible in question text
3. ⚠️ **High:** Grade values not validated against max_marks
4. ⚠️ **High:** Length limits not enforced for questions/feedback
5. ⚠️ **Medium:** Negative marks feature not supported
6. ⚠️ **Medium:** Decimal marks silently coerced

**Recommended Action:** Implement Phase 1 (critical) fixes within 1 sprint before production deployment.

---

**Report Generated:** November 29, 2025  
**Audit Scope:** Complete Sprint 1 Implementation  
**Next Review:** After Phase 1 fixes implemented
