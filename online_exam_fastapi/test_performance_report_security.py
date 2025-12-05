"""Test security of admin performance report endpoint"""
from app.database import engine, create_db_and_tables
from sqlmodel import Session, select
from app.models import User
from app.routers.admin import performance_summary_report
from unittest.mock import MagicMock
from fastapi import HTTPException

# Initialize DB
create_db_and_tables()

# Create a mock request
request_mock = MagicMock()
request_mock.url = "http://localhost:8000/admin/performance-report"

# Get session
session = Session(engine)

# Get the student user (non-admin)
student_user = session.exec(select(User).where(User.role == 'student')).first()
if not student_user:
    print("No student user found")
    session.close()
    exit(1)

print(f"Testing security: Attempting to access with student user: {student_user.name}")

# Try to call the function with a student user
try:
    response = performance_summary_report(
        request=request_mock,
        session=session,
        current_user=student_user,
    )
    print(f"✗ SECURITY ISSUE: Student was able to access admin report!")
    
except HTTPException as e:
    if e.status_code == 403:
        print(f"✓ Access denied correctly: {e.detail}")
    else:
        print(f"✗ Unexpected HTTP error {e.status_code}: {e.detail}")
except Exception as e:
    print(f"✗ Unexpected error: {type(e).__name__}: {str(e)}")
finally:
    session.close()
