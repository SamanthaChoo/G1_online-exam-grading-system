import re

with open('tests/test_essay_validation.py', 'r') as f:
    content = f.read()

content = content.replace(
    'exam = Exam(title="Test Exam", duration_minutes=60)',
    'exam = Exam(title="Test Exam", subject="Math", duration_minutes=60)'
)

with open('tests/test_essay_validation.py', 'w') as f:
    f.write(content)

print("Updated test file")
