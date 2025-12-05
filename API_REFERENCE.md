# API Endpoints Reference

## New Endpoints Created

### Student Grades API

#### GET /student/grades
**Purpose:** Display student's exam results and grades dashboard

**Method:** GET  
**Auth:** Required (Student role only)  
**Path Parameters:** None  
**Query Parameters:**
- `sort` (optional, default: "date"): Sort key
  - Values: "date", "exam", "score"
- `direction` (optional, default: "desc"): Sort direction
  - Values: "asc", "desc"
- `page` (optional, default: 1): Page number for pagination
  - Min: 1

**Request Example:**
```
GET /student/grades?sort=exam&direction=asc&page=1
Authorization: Bearer <session_token>
```

**Response:** HTML template rendered with:
- Student info (name, matric number)
- Merged essay + MCQ results table
- Pagination controls
- Sort/filter dropdown

**Success Response (200):**
```html
Renders: /app/templates/student/grades.html
Context Variables:
  - student: Student object
  - results: List[dict] with exam results
  - sort: Current sort column
  - direction: Current sort direction
  - current_page: Current page number
  - total_pages: Total pages
  - total_results: Total exam results
```

**Error Responses:**
- 403 Forbidden: User is not a student
- 403 Forbidden: No linked student record

---

### MCQ Exam Taking API

#### GET /exams/{exam_id}/mcq/start
**Purpose:** Show exam start confirmation page

**Method:** GET  
**Auth:** Optional (public view)  
**Path Parameters:**
- `exam_id` (required, int): Exam ID

**Request Example:**
```
GET /exams/5/mcq/start
```

**Response:** HTML template rendered with:
- Exam title, subject, duration
- Instructions (if available)
- Start button and cancel button

**Success Response (200):**
```html
Renders: /app/templates/exams/mcq_start.html
Context Variables:
  - exam: Exam object
  - current_user: Logged-in user (or None)
```

**Error Responses:**
- 404 Not Found: Exam doesn't exist

---

#### POST /exams/{exam_id}/mcq/start
**Purpose:** Initialize MCQ exam attempt

**Method:** POST  
**Auth:** Required (Student role only)  
**Path Parameters:**
- `exam_id` (required, int): Exam ID

**Request Example:**
```
POST /exams/5/mcq/start
Authorization: Bearer <session_token>
Content-Type: application/x-www-form-urlencoded
```

**Response:** 303 See Other (Redirect)

**Success Response (303):**
```
Location: /exams/{exam_id}/mcq/attempt
```

**Error Responses:**
- 403 Forbidden: User is not a student
- 403 Forbidden: No linked student record
- 403 Forbidden: Already answered this exam
- 404 Not Found: Exam doesn't exist

---

#### GET /exams/{exam_id}/mcq/attempt
**Purpose:** Display MCQ exam questions with countdown timer

**Method:** GET  
**Auth:** Required (Student role only)  
**Path Parameters:**
- `exam_id` (required, int): Exam ID

**Request Example:**
```
GET /exams/5/mcq/attempt
Authorization: Bearer <session_token>
```

**Response:** HTML template rendered with:
- Exam details (title, subject, duration)
- All MCQ questions with options A-D
- Countdown timer (MM:SS format)
- Submit button
- JavaScript timer logic

**Success Response (200):**
```html
Renders: /app/templates/exams/mcq_attempt.html
Context Variables:
  - exam: Exam object
  - questions: List[MCQQuestion]
  - existing_answers: Dict[question_id: selected_option]
  - student_id: Student ID
  - now_ms: Current timestamp (epoch ms)
  - current_user: Logged-in user
```

**Error Responses:**
- 403 Forbidden: User is not a student
- 404 Not Found: Exam not found
- 400 Bad Request: No questions in exam

---

#### POST /exams/{exam_id}/mcq/submit
**Purpose:** Submit MCQ answers and auto-grade

**Method:** POST  
**Auth:** Required (Student role only)  
**Content-Type:** application/x-www-form-urlencoded  
**Path Parameters:**
- `exam_id` (required, int): Exam ID

**Request Example:**
```
POST /exams/5/mcq/submit
Authorization: Bearer <session_token>
Content-Type: application/x-www-form-urlencoded

answer_1=A&answer_2=C&answer_3=B&answer_4=D&answer_5=A
```

**Request Body Format:**
- `answer_{question_id}` (string): Selected option (A, B, C, or D)
- One parameter per MCQ question

**Processing:**
1. Parse form data to extract answers
2. Validate student record
3. Save answers to MCQAnswer table
4. Auto-grade: compare with correct_option
5. Calculate score
6. Save result to MCQResult table
7. Redirect to result page

**Success Response (303):**
```
Location: /exams/{exam_id}/mcq/result
Status: 303 See Other

Side Effects:
  - Creates/updates MCQAnswer records
  - Creates/updates MCQResult record
  - Sets graded_at timestamp
```

**Error Responses:**
- 403 Forbidden: User is not a student
- 403 Forbidden: No linked student record

---

#### GET /exams/{exam_id}/mcq/result
**Purpose:** Display MCQ exam result with score and percentage

**Method:** GET  
**Auth:** Required (Student role only)  
**Path Parameters:**
- `exam_id` (required, int): Exam ID

**Request Example:**
```
GET /exams/5/mcq/result
Authorization: Bearer <session_token>
```

**Response:** HTML template rendered with:
- Score display (X/Y format)
- Percentage score with color:
  - Green (≥70%)
  - Yellow (50-69%)
  - Red (<50%)
- Submission timestamp
- Links to exam details and grades dashboard

**Success Response (200):**
```html
Renders: /app/templates/exams/mcq_result.html
Context Variables:
  - exam: Exam object
  - result: MCQResult object
  - percentage: Calculated score percentage
  - current_user: Logged-in user
```

**Error Responses:**
- 403 Forbidden: User is not a student
- 403 Forbidden: No linked student record
- 404 Not Found: Result doesn't exist

---

## Request/Response Data Structures

### MCQResult Object
```python
{
    "id": int,                      # Primary key
    "student_id": int,              # Foreign key to Student
    "exam_id": int,                 # Foreign key to Exam
    "score": int,                   # Number of correct answers
    "total_questions": int,         # Total MCQ questions
    "graded_at": datetime.utcnow()  # Timestamp
}
```

### MCQAnswer Object
```python
{
    "id": int,                      # Primary key
    "student_id": int,              # Foreign key to Student
    "exam_id": int,                 # Foreign key to Exam
    "question_id": int,             # Foreign key to MCQQuestion
    "selected_option": str,         # "A", "B", "C", or "D"
    "saved_at": datetime.utcnow()   # Timestamp
}
```

### Grade Result Object (for dashboard)
```python
{
    "exam": Exam,                   # Exam object
    "type": str,                    # "Essay" or "MCQ"
    "score": int,                   # Points earned
    "total": int,                   # Total possible points
    "percentage": float,            # Calculated percentage
    "submitted_at": datetime,       # When submitted
    "is_published": bool,           # Publication status
}
```

---

## Status Codes Reference

### Success Responses
- **200 OK** - GET requests for pages/templates
- **303 See Other** - POST redirects after form submission

### Client Error Responses
- **400 Bad Request** - Missing questions, invalid input
- **403 Forbidden** - Access denied (wrong role, not student)
- **404 Not Found** - Resource doesn't exist

---

## Authentication & Authorization

### Student Grades Access
- **Requires:** `require_login` decorator
- **Role Check:** `current_user.role == "student"`
- **Data Filter:** `student_id == current_user.student_id`

### MCQ Exam Taking
- **Start:** Optional authentication (public view)
- **Submit/Result:** `require_login` + student role
- **Enrollment Check:** If exam has course, verify student enrolled

---

## Rate Limiting & Constraints

### MCQ Submission
- **One attempt per student:** Checked before start
- **Double submit prevention:** localStorage flag
- **Auto-submit on timeout:** Automatic at 0:00

### Grade Dashboard
- **Page size:** 10 results per page (ITEMS_PER_PAGE)
- **Max sort columns:** 3 (date, exam, score)
- **No rate limit:** Queries are simple and fast

---

## Backward Compatibility

**No breaking changes to existing endpoints:**
- Essay exam taking: Unchanged
- Essay grading: Unchanged
- MCQ CRUD (lecturer/admin): Unchanged
- Course/enrollment: Unchanged
- All new endpoints are additions only

---

## Future API Considerations

Potential endpoints for Sprint 3:
- `GET /student/grades/{exam_id}` - Detailed exam result
- `GET /student/grades/export` - Export as PDF/CSV
- `GET /student/analytics` - Performance analytics
- `GET /exams/{exam_id}/mcq/review` - Review answers after submit
- `POST /exams/{exam_id}/mcq/draft` - Save draft answers
- `GET /exams/{exam_id}/mcq/draft` - Load draft answers

---

## Testing Commands

### Test MCQ Flow:
```bash
# 1. Start exam
curl -X POST http://localhost:8000/exams/1/mcq/start \
  -H "Cookie: session=<session_cookie>"

# 2. View exam
curl http://localhost:8000/exams/1/mcq/attempt \
  -H "Cookie: session=<session_cookie>"

# 3. Submit answers
curl -X POST http://localhost:8000/exams/1/mcq/submit \
  -d "answer_1=A&answer_2=B&answer_3=C" \
  -H "Cookie: session=<session_cookie>"

# 4. View result
curl http://localhost:8000/exams/1/mcq/result \
  -H "Cookie: session=<session_cookie>"
```

### Test Grades Dashboard:
```bash
curl http://localhost:8000/student/grades \
  -H "Cookie: session=<session_cookie>"

# With sorting
curl "http://localhost:8000/student/grades?sort=score&direction=desc&page=1" \
  -H "Cookie: session=<session_cookie>"
```

---

**Last Updated:** December 4, 2025  
**Status:** Ready for Production
