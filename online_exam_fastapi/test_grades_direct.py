"""Direct test of the grades endpoint function"""
from app.database import engine, create_db_and_tables
from sqlmodel import Session, select
from app.models import User
from app.routers.student import view_student_grades
from unittest.mock import MagicMock

# Initialize DB
create_db_and_tables()

# Create a mock request
request_mock = MagicMock()
request_mock.url = "http://localhost:8000/student/grades"

# Get session
session = Session(engine)

# Get the student user
student_user = session.exec(select(User).where(User.role == 'student')).first()
if not student_user:
    print("No student user found")
    session.close()
    exit(1)

print(f"Testing with user: {student_user.name} (ID: {student_user.id}, student_id: {student_user.student_id})")

# Try to call the function
try:
    response = view_student_grades(
        request=request_mock,
        session=session,
        current_user=student_user,
        sort="date",
        direction="desc",
        page=1
    )
    print(f"Success! Response type: {type(response)}")
    print(f"Response content length: {len(response.body) if hasattr(response, 'body') else 'unknown'}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
