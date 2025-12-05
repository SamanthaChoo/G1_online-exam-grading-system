"""Test the performance report endpoint"""
from app.database import engine, create_db_and_tables
from sqlmodel import Session, select
from app.models import User
from app.routers.admin import performance_summary_report
from unittest.mock import MagicMock

# Initialize DB
create_db_and_tables()

# Create a mock request
request_mock = MagicMock()
request_mock.url = "http://localhost:8000/admin/performance-report"

# Get session
session = Session(engine)

# Get or create an admin user
admin_user = session.exec(select(User).where(User.role == 'admin')).first()
if not admin_user:
    print("No admin user found")
    session.close()
    exit(1)

print(f"Testing /admin/performance-report endpoint with user: {admin_user.name}")

# Try to call the function
try:
    response = performance_summary_report(
        request=request_mock,
        session=session,
        current_user=admin_user,
    )
    print(f"✓ Success! Response type: {type(response)}")
    print(f"✓ Response content length: {len(response.body) if hasattr(response, 'body') else 'unknown'}")
    
    # Check if the response contains expected content
    response_text = response.body.decode() if hasattr(response, 'body') else ""
    if "Performance Summary Report" in response_text or "No performance data available" in response_text:
        print("✓ Template content looks correct")
    if "Student Performance Summary Report" in response_text:
        print("✓ Found performance report heading")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
