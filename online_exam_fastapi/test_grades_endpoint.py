"""Test the grades endpoint directly"""
from app.database import engine, create_db_and_tables
from sqlmodel import Session
from app.models import User
from fastapi.testclient import TestClient
from app.main import app

# Initialize DB
create_db_and_tables()

# Create test client
client = TestClient(app)

# First, login as student
login_response = client.post("/auth/login", data={"email": "laipei@university.edu.my", "password": "lpstudent123"})
print(f"Login status: {login_response.status_code}")

if login_response.status_code == 200 or login_response.status_code == 303:
    # Now try to access grades
    grades_response = client.get("/student/grades")
    print(f"Grades status: {grades_response.status_code}")
    if grades_response.status_code != 200:
        print(f"Error: {grades_response.text[:500]}")
    else:
        print("Grades page loaded successfully!")
        # Check if it contains the student name
        if "Lai Pei Yi" in grades_response.text:
            print("Found student name in response")
        if "MCQ" in grades_response.text:
            print("Found MCQ results in response")
else:
    print(f"Login failed: {login_response.status_code}")
    print(f"Response: {login_response.text[:200]}")
