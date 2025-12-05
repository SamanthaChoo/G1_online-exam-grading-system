"""Test the new /grades endpoint"""
from app.database import engine, create_db_and_tables
from sqlmodel import Session, select
from app.models import User
from app.routers.student import view_grades
from unittest.mock import MagicMock

# Initialize DB
create_db_and_tables()

# Create a mock request
request_mock = MagicMock()
request_mock.url = "http://localhost:8000/grades"

# Get session
session = Session(engine)

# Get the student user
student_user = session.exec(select(User).where(User.role == 'student')).first()
if not student_user:
    print("No student user found")
    session.close()
    exit(1)

print(f"Testing /grades endpoint with user: {student_user.name}")

# Try to call the function
try:
    response = view_grades(
        request=request_mock,
        session=session,
        current_user=student_user,
    )
    print(f"✓ Success! Response type: {type(response)}")
    print(f"✓ Response content length: {len(response.body) if hasattr(response, 'body') else 'unknown'}")
    
    # Check if the response contains expected content
    response_text = response.body.decode() if hasattr(response, 'body') else ""
    if "My Grades" in response_text:
        print("✓ Found 'My Grades' heading")
    if "Score" in response_text or "No grades available yet" in response_text:
        print("✓ Template content looks correct")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
