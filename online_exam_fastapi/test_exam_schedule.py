"""Test the exam schedule endpoint"""
from app.database import engine, create_db_and_tables
from sqlmodel import Session, select
from app.models import User, Student
from app.routers.exams import view_exam_schedule
from unittest.mock import MagicMock

# Initialize DB
create_db_and_tables()

# Create a mock request
request_mock = MagicMock()
request_mock.url = "http://localhost:8000/exams/schedule/student/4"

# Get session
session = Session(engine)

# Get a student
student = session.exec(select(Student)).first()
if not student:
    print("No students found in database")
    session.close()
    exit(1)

# Get current user (can be anyone)
current_user = session.exec(select(User)).first()

print(f"Testing /exams/schedule/student/{student.id} with student: {student.name}")

# Try to call the function
try:
    response = view_exam_schedule(
        request=request_mock,
        student_id=student.id,
        session=session,
        current_user=current_user,
    )
    print(f"✓ Success! Response type: {type(response)}")
    print(f"✓ Response content length: {len(response.body) if hasattr(response, 'body') else 'unknown'}")
    
    # Check if the response contains expected content
    response_text = response.body.decode() if hasattr(response, 'body') else ""
    if "Exam Schedule" in response_text:
        print("✓ Found 'Exam Schedule' heading")
    if student.name in response_text:
        print(f"✓ Found student name '{student.name}'")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
