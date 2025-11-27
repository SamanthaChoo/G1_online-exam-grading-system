# Online Examination & Grading System - Sprint 1
## My Responsibilities Documentation

---

## 📋 SPRINT 1 USER STORIES IMPLEMENTED

### ✅ 1. Create Essay Questions
**As a lecturer**, I want to add long-answer/essay-type questions to an exam,  
so that I can include subjective questions requiring manual grading.

**Implementation:**
- Route: `GET /essays/{exam_id}/add` - Display form
- Route: `POST /essays/{exam_id}/add` - Save question
- Route: `GET /essays/{exam_id}/view` - List all questions
- Model: `EssayQuestion` table with exam_id, question_text, max_marks

---

### ✅ 2. Manual Grade Essay Questions
**As a lecturer**, I want to manually grade essay responses,  
so that I can assign marks for subjective questions.

**Implementation:**
- Route: `GET /grading/{exam_id}/submissions` - List student submissions
- Route: `GET /grading/{exam_id}/{student_id}` - View submission details
- Route: `POST /grading/{exam_id}/{student_id}` - Save grades
- Model: `EssaySubmission` table with marks_awarded, grader_comments

---

### ✅ 3. Auto Submit When Time Ends
**As a lecturer**, I want the system to auto-submit answers when time ends  
so that students do not exceed the designated exam duration.

**Implementation:**
- JavaScript countdown timer in `take.html`
- Auto-submit triggered at 0 seconds
- Route: `POST /exam/{exam_id}/auto-submit` - Handle auto-submission
- Model: `ExamAttempt.auto_submitted` flag tracks auto-submissions

---

### ✅ 4. One Attempt Enforcement
**As a lecturer**, I want the system to enforce a single-attempt rule per exam,  
so that students cannot restart after submitting or timeout.

**Implementation:**
- Database constraint: UNIQUE(exam_id, student_id) on ExamAttempt
- Route: `GET /exam/{exam_id}/start` checks existing attempts
- Shows "Already Attempted" page if submitted
- Shows "Auto Submitted" page if time expired
- Prevents re-entry after submission

---

## 🗂️ PROJECT STRUCTURE

```
app/
├── __init__.py
├── main.py                 # FastAPI app with routers
├── models.py              # SQLModel entities
├── database.py            # Database session management
├── routers/
│   ├── __init__.py
│   ├── essay.py          # Essay question routes
│   ├── exam_taking.py    # Exam taking & auto-submit
│   └── grading.py        # Manual grading routes
└── templates/
    ├── base.html         # Base template
    ├── essays/
    │   ├── add.html      # Add question form
    │   └── list.html     # View questions
    ├── exams/
    │   ├── take.html     # Take exam (with timer)
    │   ├── already_attempted.html
    │   ├── auto_submitted.html
    │   └── confirmation.html
    ├── grading/
    │   ├── list.html     # Student submissions
    │   └── detail.html   # Grade submission
    └── errors/
        └── 404.html
```

---

## 💾 DATABASE SCHEMA

### EssayQuestion
```sql
CREATE TABLE essayquestion (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    max_marks INTEGER NOT NULL,
    created_at DATETIME,
    FOREIGN KEY (exam_id) REFERENCES exam(id)
);
```

### EssaySubmission
```sql
CREATE TABLE essaysubmission (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    answer_text TEXT,
    submitted_at DATETIME,
    marks_awarded INTEGER,
    graded_at DATETIME,
    grader_comments TEXT,
    FOREIGN KEY (exam_id) REFERENCES exam(id),
    FOREIGN KEY (student_id) REFERENCES student(id),
    FOREIGN KEY (question_id) REFERENCES essayquestion(id),
    UNIQUE (exam_id, student_id, question_id)
);
```

### ExamAttempt
```sql
CREATE TABLE examattempt (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    started_at DATETIME,
    ended_at DATETIME,
    submitted BOOLEAN DEFAULT FALSE,
    auto_submitted BOOLEAN DEFAULT FALSE,
    remaining_seconds INTEGER,
    FOREIGN KEY (exam_id) REFERENCES exam(id),
    FOREIGN KEY (student_id) REFERENCES student(id),
    UNIQUE (exam_id, student_id)
);
```

---

## 🚀 SETUP & RUN INSTRUCTIONS

### 1. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Server
```bash
uvicorn app.main:app --reload
```

Server will start at: `http://127.0.0.1:8000`

---

## 🧪 TESTING USER STORIES

### Test User Story 1: Create Essay Questions
1. Navigate to: `http://127.0.0.1:8000/essays/1/add` (assuming exam_id=1 exists)
2. Fill in:
   - Question Text: "Discuss the impact of climate change on global ecosystems."
   - Max Marks: 20
3. Click "Add Question"
4. Verify: Question appears in `/essays/1/view`

### Test User Story 2: Manual Grade Essay Questions
1. Navigate to: `http://127.0.0.1:8000/grading/1/submissions`
2. Click "Grade" on a student submission
3. Enter marks and comments for each question
4. Click "Save All Grades"
5. Verify: Grades saved and visible in submission list

### Test User Story 3: Auto Submit When Time Ends
1. Navigate to: `http://127.0.0.1:8000/exam/1/start?student_id=1`
2. Wait for countdown timer to reach 0
3. Verify: Auto-submit modal appears
4. Verify: Redirected to auto-submitted page
5. Verify: `auto_submitted=True` in database

### Test User Story 4: One Attempt Enforcement
1. Complete an exam (submit or let timer expire)
2. Try to access `/exam/1/start?student_id=1` again
3. Verify: "Already Attempted" or "Auto Submitted" page shown
4. Verify: Cannot re-enter exam

---

## 📊 API ENDPOINTS SUMMARY

| Method | Endpoint | Purpose | User Story |
|--------|----------|---------|------------|
| GET | `/essays/{exam_id}/add` | Show add question form | US1 |
| POST | `/essays/{exam_id}/add` | Create essay question | US1 |
| GET | `/essays/{exam_id}/view` | List essay questions | US1 |
| GET | `/exam/{exam_id}/start` | Start exam (check attempts) | US3, US4 |
| POST | `/exam/{exam_id}/submit` | Manual submission | - |
| POST | `/exam/{exam_id}/auto-submit` | Auto-submit on timeout | US3 |
| GET | `/grading/{exam_id}/submissions` | List submissions | US2 |
| GET | `/grading/{exam_id}/{student_id}` | View student answers | US2 |
| POST | `/grading/{exam_id}/{student_id}` | Save grades | US2 |

---

## 🔄 SPRINT 2 ENHANCEMENTS (Planned)

### Authentication & Authorization
- Add user login/logout
- Role-based access control (student/lecturer)
- Session management

### Essay Features
- Question editing/deletion
- Question bank/templates
- Bulk import from Excel/CSV
- Rich text editor for questions

### Exam Taking
- Pause/resume functionality
- Draft answer saving
- Word count display
- Browser tab monitoring
- Webcam proctoring

### Grading
- Rubric-based grading
- AI-assisted grading suggestions
- Bulk grading interface
- Grade moderation workflow
- Statistical reports

### Database
- Migrate to PostgreSQL
- Add Alembic migrations
- Connection pooling
- Read replicas

---

## 🐛 KNOWN LIMITATIONS (Sprint 1)

1. **No Authentication**: student_id passed as query parameter
2. **No Validation**: Limited input validation
3. **No Error Messages**: Flash messages not implemented
4. **No Edit/Delete**: Questions cannot be edited after creation
5. **Simple UI**: Basic Bootstrap styling
6. **SQLite Only**: Not production-ready database
7. **No Audit Trail**: No logging of grade changes
8. **No Notifications**: No email alerts for submissions

---

## 📝 SPRINT 1 DOCUMENTATION FOR TEAM

### For Other Team Members

**Assumed Models (Managed by others):**
- `Student` - Has id, name, email
- `Exam` - Has id, title, description, duration_minutes

**My Dependencies:**
- Need `Exam` creation module from team member X
- Need `Student` registration from team member Y

**Integration Points:**
- My routes can be accessed after exam creation
- Student ID will come from auth system in Sprint 2

### Code Quality
- ✅ Type hints on all functions
- ✅ Docstrings explaining each route
- ✅ Comments for Sprint 2 enhancements
- ✅ Clean separation of concerns
- ✅ RESTful API design

---

## 🎯 SPRINT 1 COMPLETION CHECKLIST

- [x] EssayQuestion model created
- [x] EssaySubmission model created
- [x] ExamAttempt model created with UNIQUE constraint
- [x] Essay question creation routes (GET/POST)
- [x] Essay question listing route
- [x] Exam taking route with attempt checking
- [x] JavaScript countdown timer
- [x] Auto-submit functionality
- [x] Manual submission route
- [x] Grading submission list route
- [x] Grading detail route (view answers)
- [x] Grade saving route
- [x] All Jinja2 templates created
- [x] Bootstrap styling applied
- [x] User Story 1 tested ✅
- [x] User Story 2 tested ✅
- [x] User Story 3 tested ✅
- [x] User Story 4 tested ✅

---

## 📞 CONTACT & QUESTIONS

For Sprint 1 questions regarding:
- Essay question management
- Manual grading
- Auto-submit functionality
- One attempt enforcement

Contact: [Your Name]
Email: [Your Email]
Sprint Review Date: [Date]

---

**Sprint 1 Status: COMPLETE ✅**
**Ready for Sprint 2 Planning**
