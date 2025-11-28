# Online Examination & Grading System - Sprint 1

## 🎯 Sprint 1 Features (My Responsibilities)

This implementation covers the following user stories:

1. ✅ **Create Essay Questions** - Add long-answer questions to exams
2. ✅ **Manual Grade Essay Questions** - Grade student essay responses
3. ✅ **Auto Submit When Time Ends** - Automatic submission on timeout
4. ✅ **One Attempt Enforcement** - Prevent multiple exam attempts

---

## 🚀 Quick Start

### Option 1: Using Quick Start Script (Recommended)

**Windows:**
```cmd
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

### Option 2: Manual Setup

1. **Create Virtual Environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Seed Database (Optional)**
```bash
python seed_data.py
```

4. **Run Server**
```bash
uvicorn app.main:app --reload
```

5. **Access Application**
```
http://127.0.0.1:8000
```

---

## 📁 Project Structure

```
app/
├── main.py                 # FastAPI application
├── models.py              # SQLModel database models
├── database.py            # Database configuration
├── routers/
│   ├── essay.py          # Essay question routes
│   ├── exam_taking.py    # Exam taking & auto-submit
│   └── grading.py        # Manual grading routes
└── templates/
    ├── base.html         # Base template
    ├── essays/           # Essay question templates
    ├── exams/            # Exam taking templates
    ├── grading/          # Grading templates
    └── errors/           # Error pages
```

---

## 🧪 Testing User Stories

### US1: Create Essay Questions
1. Navigate to `http://127.0.0.1:8000/essays/1/add`
2. Fill in question text and max marks
3. Submit and verify in question list

### US2: Manual Grade Essay Questions
1. Student takes exam (next step)
2. Navigate to `http://127.0.0.1:8000/grading/1/submissions`
3. Click "Grade" on submission
4. Enter marks and comments
5. Save grades

### US3: Auto Submit When Time Ends
1. Navigate to `http://127.0.0.1:8000/exam/1/start?student_id=1`
2. Wait for countdown timer to reach 0
3. Verify auto-submission
4. Check `auto_submitted=True` in database

### US4: One Attempt Enforcement
1. Complete an exam (submit or timeout)
2. Try accessing exam again
3. Verify "Already Attempted" message
4. Confirm cannot re-enter exam

---

## 📊 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/essays/{exam_id}/add` | Add question form |
| POST | `/essays/{exam_id}/add` | Create question |
| GET | `/essays/{exam_id}/view` | List questions |
| GET | `/exam/{exam_id}/start` | Start exam |
| POST | `/exam/{exam_id}/submit` | Submit exam |
| POST | `/exam/{exam_id}/auto-submit` | Auto-submit |
| GET | `/grading/{exam_id}/submissions` | List submissions |
| GET | `/grading/{exam_id}/{student_id}` | View answers |
| POST | `/grading/{exam_id}/{student_id}` | Save grades |

---

## 💾 Database Models

### EssayQuestion
- `id` - Primary key
- `exam_id` - Foreign key to Exam
- `question_text` - Question content
- `max_marks` - Maximum marks

### EssaySubmission
- `id` - Primary key
- `exam_id`, `student_id`, `question_id` - Foreign keys
- `answer_text` - Student's answer
- `marks_awarded` - Awarded marks
- `grader_comments` - Feedback
- Unique constraint: (exam_id, student_id, question_id)

### ExamAttempt
- `id` - Primary key
- `exam_id`, `student_id` - Foreign keys
- `started_at`, `ended_at` - Timestamps
- `submitted` - Manual submission flag
- `auto_submitted` - Auto-submission flag
- Unique constraint: (exam_id, student_id)

---

## 🔧 Tech Stack

- **Backend:** FastAPI
- **Database:** SQLModel + SQLite
- **Templates:** Jinja2
- **Frontend:** Bootstrap 5 (BootstrapMade)
- **Server:** Uvicorn

---

## 📝 Sprint 2 Enhancements (Planned)

- Authentication & authorization
- Rich text editor for questions
- Rubric-based grading
- AI-assisted grading
- Question bank/templates
- Draft answer saving
- Grade statistics
- PostgreSQL migration

---

## 📖 Documentation

See [SPRINT1_DOCUMENTATION.md](SPRINT1_DOCUMENTATION.md) for:
- Detailed user story implementation
- Database schema
- Testing procedures
- Known limitations
- Integration notes

---

## 🐛 Known Limitations (Sprint 1)

- No authentication (student_id as query param)
- Limited input validation
- No flash messages
- No question editing
- SQLite only (not production-ready)

---

## 📞 Support

For questions about Sprint 1 implementation:
- Essay question management
- Manual grading
- Auto-submit functionality
- One attempt enforcement

---

**Status:** ✅ Sprint 1 Complete | Ready for Sprint 2
