# Sprint 1: MCQ Management + Auto-Grading + Exam Execution

## 🎯 Overview

This Sprint implements a complete **Online Examination & Grading System** with:
- MCQ Questions CRUD Management
- Exam Start Page with Countdown Timer
- Exam Paper Display with Auto-save
- Auto-submit when time expires
- Auto-grading system

**Tech Stack:**
- Python 3.x
- FastAPI
- Uvicorn
- SQLModel ORM + SQLite
- Jinja2 Templates
- Bootstrap 5 (BootstrapMade "MySchool" template)

---

## 📦 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Create Virtual Environment

```powershell
# Navigate to project directory
cd c:\Users\samantha\Desktop\G1_online-exam-grading-system\G1_online-exam-grading-system

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

### Step 2: Install Dependencies

```powershell
pip install -r requirements.txt
```

### Step 3: Initialize Database

The database will be automatically initialized when you first run the application. It creates a SQLite database file `exam_system.db` in the project root.

### Step 4: Run the Application

```powershell
# Make sure you're in the src directory
cd src

# Run with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at: **http://localhost:8000**

---

## 🗂 Project Structure

```
G1_online-exam-grading-system/
│
├── src/
│   ├── main.py                      # Main FastAPI application
│   └── app/
│       ├── __init__.py
│       ├── models.py                # SQLModel database models
│       ├── database.py              # Database configuration
│       └── routers/
│           ├── __init__.py
│           ├── questions.py         # MCQ CRUD routes
│           └── exam_execution.py   # Exam execution routes
│
├── templates/
│   ├── index.html                   # Home page
│   ├── questions/
│   │   ├── list.html               # List all MCQ questions
│   │   ├── form.html               # Create/Edit question form
│   │   └── detail.html             # View question details
│   └── exam_execution/
│       ├── start.html              # Exam start page with countdown
│       ├── paper.html              # Exam paper with auto-save
│       └── submitted.html          # Exam submitted confirmation
│
├── assets/                          # BootstrapMade static files
│   ├── css/
│   ├── js/
│   ├── img/
│   └── vendor/
│
├── requirements.txt                 # Python dependencies
├── exam_system.db                  # SQLite database (auto-created)
└── README.md                       # This file
```

---

## 🚀 Features Implemented

### 1. MCQ Questions CRUD Management

**For Lecturers** - Create, Read, Update, Delete MCQ questions

#### Routes:
- `GET /questions/?exam_id={id}` - List all questions for an exam
- `GET /questions/new?exam_id={id}` - Show create question form
- `POST /questions/new?exam_id={id}` - Create new question
- `GET /questions/{id}` - View question details
- `GET /questions/{id}/edit` - Show edit question form
- `POST /questions/{id}/edit` - Update question
- `POST /questions/{id}/delete` - Delete question

#### Features:
- Each question has:
  - Question text
  - 4 options (A, B, C, D)
  - Correct answer selection
  - Optional explanation
  - Linked to specific exam

---

### 2. Exam Start Page with Countdown

**For Students** - Join exam window management

#### Route:
- `GET /exam/start/{exam_id}` - Exam start page

#### Features:
- Shows exam title, start time, duration
- Countdown timer until exam starts
- Join button appears 30 minutes before start time
- Button enabled only when exam starts
- Real-time JavaScript countdown

---

### 3. Exam Paper Display

**For Students** - Take the exam

#### Route:
- `GET /exam/paper/{exam_id}?student_id={id}` - Exam paper page

#### Features:
- Displays all MCQ questions
- Radio button selection for answers
- Timer bar showing remaining time
- Color changes based on time remaining:
  - Blue: Normal
  - Yellow: ≤5 minutes remaining
  - Red (pulsing): ≤1 minute remaining
- Loads previously saved answers on refresh
- Manual submit button

---

### 4. Auto-save Answers

**Automatic** - Background saving every 60 seconds

#### Route:
- `POST /exam/paper/{exam_id}/autosave` - Auto-save endpoint

#### Features:
- JavaScript timer calls autosave every 60 seconds
- Saves current answers to database
- Shows "Answers Saved" indicator
- Upserts answers (update if exists, insert if new)
- Prevents data loss on refresh

---

### 5. Auto-submit & Auto-grading

**Automatic** - When time expires or manual submit

#### Routes:
- `POST /exam/paper/{exam_id}/submit` - Submit and grade exam
- `GET /exam/submitted/{exam_id}?student_id={id}` - Results page

#### Features:
- Auto-submits when timer reaches 0
- Compares student answers with correct answers
- Calculates percentage score
- Stores result in ExamResult table
- Shows:
  - Final score percentage
  - Correct answers count
  - Total questions
  - Performance message based on score

---

## 🗄 Database Models

### 1. Exam
```python
- id: int (PK)
- title: str
- description: str (optional)
- start_time: datetime
- duration_minutes: int
- created_at: datetime
- updated_at: datetime
```

### 2. MCQQuestion
```python
- id: int (PK)
- exam_id: int (FK)
- question_text: str
- option_a: str
- option_b: str
- option_c: str
- option_d: str
- correct_option: str (A/B/C/D)
- explanation: str (optional)
- created_at: datetime
```

### 3. StudentAnswer
```python
- id: int (PK)
- student_id: int
- exam_id: int (FK)
- question_id: int (FK)
- selected_option: str (A/B/C/D)
- updated_at: datetime
```

### 4. ExamResult
```python
- id: int (PK)
- student_id: int
- exam_id: int (FK)
- score: float (percentage)
- total_questions: int
- correct_answers: int
- submitted_at: datetime
```

---

## 🌐 Complete URL Map

### Home
- `GET /` - Home page

### MCQ Questions Management
- `GET /questions/?exam_id={id}` - List questions
- `GET /questions/new?exam_id={id}` - Create question form
- `POST /questions/new?exam_id={id}` - Create question
- `GET /questions/{id}` - View question details
- `GET /questions/{id}/edit` - Edit question form
- `POST /questions/{id}/edit` - Update question
- `POST /questions/{id}/delete` - Delete question

### Exam Execution
- `GET /exam/start/{exam_id}` - Exam start page
- `GET /exam/paper/{exam_id}?student_id={id}` - Exam paper
- `POST /exam/paper/{exam_id}/autosave` - Auto-save answers (AJAX)
- `POST /exam/paper/{exam_id}/submit` - Submit exam (AJAX)
- `GET /exam/submitted/{exam_id}?student_id={id}` - Results page

---

## 📝 Testing the Application

### 1. Create Sample Exam Data

You'll need to manually insert a sample exam into the database first. Use the following Python script:

```python
# create_sample_exam.py
from datetime import datetime, timedelta
from sqlmodel import Session, create_engine
from app.models import Exam

engine = create_engine("sqlite:///./exam_system.db")

with Session(engine) as session:
    # Create a sample exam starting in 5 minutes
    exam = Exam(
        title="Python Programming Midterm",
        description="Test your Python knowledge",
        start_time=datetime.utcnow() + timedelta(minutes=5),
        duration_minutes=30
    )
    session.add(exam)
    session.commit()
    print(f"✅ Created exam with ID: {exam.id}")
```

Run it:
```powershell
cd src
python create_sample_exam.py
```

### 2. Test MCQ CRUD

1. Go to `http://localhost:8000/questions/?exam_id=1`
2. Click "Add New Question"
3. Fill in question details
4. Create multiple questions (at least 5 for a good test)

### 3. Test Exam Execution

1. Go to `http://localhost:8000/exam/start/1`
2. Wait for countdown (or adjust exam start_time in database)
3. Click "Start Exam"
4. Answer questions
5. Wait for auto-save indicator (60 seconds)
6. Submit manually or wait for auto-submit

---

## 🔧 Configuration

### Change Database Location

Edit `src/app/database.py`:
```python
DATABASE_URL = "sqlite:///./exam_system.db"  # Change path here
```

### Change Auto-save Interval

Edit `templates/exam_execution/paper.html`:
```javascript
setInterval(autoSave, 60000);  // Change 60000 to desired milliseconds
```

### Change Early Join Window

Edit `src/app/routers/exam_execution.py`:
```python
early_join_window = 30 * 60  # Change 30 to desired minutes
```

---

## 🐛 Troubleshooting

### Database Errors
```powershell
# Delete and recreate database
rm exam_system.db
# Restart the application - it will recreate tables
```

### Import Errors
```powershell
# Make sure you're in the src directory
cd src
# And run from there
uvicorn main:app --reload
```

### Port Already in Use
```powershell
# Use a different port
uvicorn main:app --reload --port 8001
```

---

## 📋 Sprint 1 Checklist

- ✅ MCQ Questions CRUD (Create, Read, Update, Delete)
- ✅ Question form with 4 options + correct answer
- ✅ Exam start page with countdown timer
- ✅ Join button available 30 minutes before start
- ✅ Exam paper with all questions displayed
- ✅ Radio button selection for answers
- ✅ Auto-save every 60 seconds
- ✅ Timer showing remaining time
- ✅ Auto-submit when time expires
- ✅ Auto-grading comparing answers
- ✅ Results page with score and breakdown
- ✅ Bootstrap 5 styling (BootstrapMade template)
- ✅ SQLModel + SQLite database
- ✅ All routes properly documented

---

## 🚀 Next Steps (Sprint 2)

Sprint 2 will add:
- User authentication (Students, Lecturers, Admin roles)
- Session management
- Role-based access control
- Exam assignment to specific students
- Enhanced result viewing with answer review
- Export results to CSV/PDF

---

## 👥 Development Team

**Sprint 1 Developer:** Samantha
**Branch:** MCQ-CRUD

---

## 📄 License

This project is developed as part of academic coursework.

---

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section
2. Review the error logs in the console
3. Contact the development team

---

**Last Updated:** November 27, 2025
**Version:** 1.0.0 (Sprint 1)
