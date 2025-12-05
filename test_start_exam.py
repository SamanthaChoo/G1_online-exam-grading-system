#!/usr/bin/env python3
"""Test the exam start endpoint."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "online_exam_fastapi"))
os.chdir(os.path.join(os.path.dirname(__file__), "online_exam_fastapi"))

from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)

# Test the endpoint
response = client.get("/exams/1/start?student_id=4", follow_redirects=False)
print(f"Status Code: {response.status_code}")
print(f"URL: {response.url}")
if response.status_code in [302, 303]:
    print(f"Redirect Location: {response.headers.get('location')}")
else:
    print(f"Response: {response.text[:200]}")
