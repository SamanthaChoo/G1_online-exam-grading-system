# 🚀 Quick Start Guide - Sprint 1

## Installation (5 minutes)

### 1. Create Virtual Environment
```powershell
cd c:\Users\samantha\Desktop\G1_online-exam-grading-system\G1_online-exam-grading-system
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

## Running the Application

### 3. Start Server
```powershell
cd src
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Create Sample Data (Optional but Recommended)
In a new terminal:
```powershell
cd src
python create_sample_data.py
```

## Testing the Features

### Access Points:
- **Home Page:** http://localhost:8000
- **Exam Start:** http://localhost:8000/exam/start/1
- **Manage Questions:** http://localhost:8000/questions/?exam_id=1

### Test Flow:
1. ✅ Visit Exam Start page - see countdown timer
2. ✅ Wait for countdown or adjust start_time in DB
3. ✅ Click "Start Exam" button
4. ✅ Answer MCQ questions
5. ✅ Wait 60 seconds to see auto-save indicator
6. ✅ Submit exam or let timer expire
7. ✅ View results with score breakdown

### Managing Questions:
1. ✅ Go to `/questions/?exam_id=1`
2. ✅ Click "Add New Question"
3. ✅ Fill form with question and 4 options
4. ✅ Select correct answer (A/B/C/D)
5. ✅ Add optional explanation
6. ✅ Submit to create question

## Troubleshooting

### "Module not found" errors?
```powershell
# Make sure you're in src directory and venv is activated
cd src
python -c "import fastapi; print('✅ Dependencies OK')"
```

### Database issues?
```powershell
# Delete and recreate
rm exam_system.db
# Restart server - it will recreate tables
```

### Port already in use?
```powershell
# Use different port
uvicorn main:app --reload --port 8001
```

## 📋 Quick Reference

### Sprint 1 Features
- ✅ MCQ CRUD Management
- ✅ Exam Start with Countdown (30 min window)
- ✅ Exam Paper Display
- ✅ Auto-save every 60 seconds
- ✅ Auto-submit when time expires
- ✅ Auto-grading system
- ✅ Results page with score

### Key URLs
```
GET  /                                    - Home
GET  /questions/?exam_id=1                - List questions
GET  /questions/new?exam_id=1             - Create question
GET  /questions/{id}                      - View question
GET  /questions/{id}/edit                 - Edit question
POST /questions/{id}/delete               - Delete question
GET  /exam/start/{exam_id}                - Exam start page
GET  /exam/paper/{exam_id}?student_id=1   - Exam paper
POST /exam/paper/{exam_id}/autosave       - Auto-save (AJAX)
POST /exam/paper/{exam_id}/submit         - Submit exam (AJAX)
GET  /exam/submitted/{exam_id}            - Results page
```

### Database Models
- `Exam` - Exam details (title, start_time, duration)
- `MCQQuestion` - Question with 4 options + correct answer
- `StudentAnswer` - Student's selected answers
- `ExamResult` - Final score and submission time

---

**Need Help?** Check SPRINT1_README.md for detailed documentation!
