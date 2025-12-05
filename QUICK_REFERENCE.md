# Quick Reference: Key Code Changes

## 1. MCQ Timer JavaScript Pattern (in mcq_attempt.html)

```javascript
// Configuration
const examId = {{ exam.id | tojson }};
const durationMinutes = {{ (exam.duration_minutes or 60) | tojson }};
const nowMs = {{ now_ms | tojson }};

// Calculate end time
const startTime = new Date(nowMs);
const endTime = new Date(startTime.getTime() + durationMinutes * 60000);

// Update countdown every second
function updateCountdown() {
  const now = new Date();
  let diff = Math.max(0, Math.floor((endTime - now) / 1000));
  const mins = Math.floor(diff / 60).toString().padStart(2, '0');
  const secs = (diff % 60).toString().padStart(2, '0');
  
  document.getElementById('countdown').textContent = mins + ':' + secs;
  
  if (diff <= 0) {
    clearInterval(timer);
    doAutoSubmit();  // Auto-submit form when time expires
  }
}

let timer = setInterval(updateCountdown, 1000);
```

---

## 2. MCQ Auto-Submit Endpoint (in mcq.py)

```python
@router.post("/{exam_id}/mcq/submit")
async def submit_mcq_attempt(
    exam_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_login),
):
    """Submit MCQ answers and auto-grade."""
    # Read form data
    form = await request.form()
    
    # Collect answers
    answers_dict = {}
    for key, value in form.items():
        if key.startswith("answer_"):
            qid = int(key.split("_")[1])
            answers_dict[qid] = value
    
    # Save to MCQAnswer table
    for qid, selected_option in answers_dict.items():
        answer = MCQAnswer(
            student_id=student_id,
            exam_id=exam_id,
            question_id=qid,
            selected_option=selected_option,
            saved_at=datetime.utcnow(),
        )
        session.add(answer)
    
    # Auto-grade by comparing with correct_option
    score = 0
    for question in questions:
        selected = answers_dict.get(question.id, "")
        if selected and selected.upper() == question.correct_option:
            score += 1
    
    # Save result
    result = MCQResult(
        student_id=student_id,
        exam_id=exam_id,
        score=score,
        total_questions=len(questions),
        graded_at=datetime.utcnow(),
    )
    session.add(result)
    session.commit()
    
    return RedirectResponse(url=f"/exams/{exam_id}/mcq/result")
```

---

## 3. Student Grades Query Logic (in student.py)

```python
@router.get("/student/grades")
def view_student_grades(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_login),
    sort: Optional[str] = Query("date", regex="^(date|exam|score)$"),
    direction: Optional[str] = Query("desc", regex="^(asc|desc)$"),
    page: Optional[int] = Query(1, ge=1),
):
    """Display all exam results for student."""
    
    results = []
    
    # Get essay attempts with grades
    essay_attempts = session.exec(
        select(ExamAttempt).where(
            (ExamAttempt.student_id == student_id)
            & (ExamAttempt.status.in_(["submitted", "timed_out"]))
        )
    ).all()
    
    for attempt in essay_attempts:
        answers = session.exec(
            select(EssayAnswer).where(EssayAnswer.attempt_id == attempt.id)
        ).all()
        
        # Essay is "published" when any answer has marks_awarded
        is_graded = any(a.marks_awarded is not None for a in answers)
        
        results.append({
            "exam": exam,
            "type": "Essay",
            "score": total_marks,
            "total": total_possible,
            "percentage": (total_marks / total_possible * 100) if total_possible > 0 else 0,
            "is_published": is_graded,
        })
    
    # Get MCQ results
    mcq_results = session.exec(
        select(MCQResult).where(MCQResult.student_id == student_id)
    ).all()
    
    for mcq_result in mcq_results:
        results.append({
            "exam": exam,
            "type": "MCQ",
            "score": mcq_result.score,
            "total": mcq_result.total_questions,
            "percentage": (mcq_result.score / mcq_result.total_questions * 100),
            "is_published": True,  # MCQ always published (auto-graded)
        })
    
    # Sort and paginate
    if sort == "date":
        results.sort(key=lambda x: x["submitted_at"], reverse=(direction == "desc"))
    elif sort == "exam":
        results.sort(key=lambda x: x["exam"].title.lower(), reverse=(direction == "desc"))
    elif sort == "score":
        results.sort(key=lambda x: x["percentage"], reverse=(direction == "desc"))
    
    # Paginate
    total_results = len(results)
    paginated = results[(page-1)*ITEMS_PER_PAGE : page*ITEMS_PER_PAGE]
    
    return templates.TemplateResponse("student/grades.html", context)
```

---

## 4. Grade Dashboard Color Coding (in grades.html)

```html
<!-- Color-coded percentage badge -->
{% set score_badge = "bg-success" if result.percentage >= 70 else "bg-warning" if result.percentage >= 50 else "bg-danger" %}
<span class="badge {{ score_badge }}">{{ "%.1f"|format(result.percentage) }}%</span>

<!-- Result: 
     ✅ Green badge if ≥70%
     ⚠️ Yellow badge if 50-69%
     ❌ Red badge if <50%
-->
```

---

## 5. Navigation Link (base.html)

```html
<!-- Main navigation for students -->
{% if current_user and current_user.role == 'student' %}
  <li><a href="/student/grades">My Grades</a></li>
{% endif %}

<!-- Dropdown menu -->
{% if current_user.role == "student" %}
  <li><a class="dropdown-item" href="/student/grades">My Grades</a></li>
{% endif %}
```

---

## 6. Import Statement Update (main.py)

```python
from app.routers import student as student_router_module

# Register router
app.include_router(student_router_module.router, tags=["student"])
```

---

## 7. Form Structure in MCQ Attempt Template

```html
<form id="mcq-form" method="post" action="/exams/{{ exam.id }}/mcq/submit">
  {% for question in questions %}
    <!-- Radio buttons named: answer_{question_id} -->
    <input type="radio" name="answer_{{ question.id }}" value="A">
    <input type="radio" name="answer_{{ question.id }}" value="B">
    <input type="radio" name="answer_{{ question.id }}" value="C">
    <input type="radio" name="answer_{{ question.id }}" value="D">
  {% endfor %}
  <button type="submit" id="submit-btn">Submit Exam</button>
</form>
```

Backend automatically converts `request.form()` into `answers_dict`:
```python
answers_dict = {
    question_id_1: "A",
    question_id_2: "C",
    ...
}
```

---

## 8. Model Usage

```python
# Save MCQ answer
answer = MCQAnswer(
    student_id=student_id,
    exam_id=exam_id,
    question_id=qid,
    selected_option=value,  # "A", "B", "C", or "D"
    saved_at=datetime.utcnow(),
)

# Save MCQ result
result = MCQResult(
    student_id=student_id,
    exam_id=exam_id,
    score=correct_count,  # Number of correct answers
    total_questions=len(questions),
    graded_at=datetime.utcnow(),
)
```

---

## 9. Checking Publication Status (in student.py)

```python
# Essay: Published only when graded
is_essay_published = any(a.marks_awarded is not None for a in answers)

# MCQ: Always published (auto-graded)
is_mcq_published = True
```

---

## 10. Timer Color Change Logic

```javascript
// Initial: Yellow (warning)
<div class="alert alert-warning">
  <strong>Time remaining:</strong> <span id="countdown">--:--</span>
</div>

// When ≤5 minutes: Switch to Red (danger)
if (diff <= 300) {  // 300 seconds = 5 minutes
  countdown.parentElement.classList.remove('alert-warning');
  countdown.parentElement.classList.add('alert-danger');
}
```

---

**Key Takeaways:**
- Timer uses server-side epoch (not client time) to prevent manipulation
- Auto-submit happens on both timeout AND form submission
- Grades combine essay + MCQ into unified view
- Publication determined by grading status (essay) or auto-grade (MCQ)
- Sorting flexible: date, name, or score
- Form radio naming convention: `answer_{question_id}`
- localStorage prevents double-submit
- All student data filtered by `student_id`
