"""
Create Sample Exam Data
Helper script to initialize the database with sample exam and questions
"""

import sys
sys.path.append('.')

from datetime import datetime, timedelta
from sqlmodel import Session, create_engine
from app.models import Exam, MCQQuestion

# Database URL
DATABASE_URL = "sqlite:///./exam_system.db"
engine = create_engine(DATABASE_URL)


def create_sample_exam():
    """Create a sample exam"""
    with Session(engine) as session:
        # Create exam starting in 5 minutes for testing
        exam = Exam(
            title="Python Programming Midterm Exam",
            description="Test your knowledge of Python fundamentals, data structures, and OOP concepts",
            start_time=datetime.utcnow() + timedelta(minutes=5),
            duration_minutes=30
        )
        session.add(exam)
        session.commit()
        session.refresh(exam)
        
        print(f"✅ Created exam: {exam.title}")
        print(f"   ID: {exam.id}")
        print(f"   Start Time: {exam.start_time}")
        print(f"   Duration: {exam.duration_minutes} minutes")
        
        return exam.id


def create_sample_questions(exam_id):
    """Create sample MCQ questions for the exam"""
    with Session(engine) as session:
        questions = [
            {
                "question_text": "What is the output of: print(type([]))?",
                "option_a": "<class 'list'>",
                "option_b": "<class 'tuple'>",
                "option_c": "<class 'dict'>",
                "option_d": "<class 'set'>",
                "correct_option": "A",
                "explanation": "Empty square brackets [] create a list object in Python"
            },
            {
                "question_text": "Which keyword is used to define a function in Python?",
                "option_a": "function",
                "option_b": "def",
                "option_c": "func",
                "option_d": "define",
                "correct_option": "B",
                "explanation": "The 'def' keyword is used to define functions in Python"
            },
            {
                "question_text": "What is the result of: 10 // 3?",
                "option_a": "3.33",
                "option_b": "3",
                "option_c": "4",
                "option_d": "3.0",
                "correct_option": "B",
                "explanation": "The // operator performs floor division, returning only the integer part"
            },
            {
                "question_text": "Which of the following is mutable in Python?",
                "option_a": "tuple",
                "option_b": "string",
                "option_c": "list",
                "option_d": "integer",
                "correct_option": "C",
                "explanation": "Lists are mutable, meaning their contents can be changed after creation"
            },
            {
                "question_text": "What does the 'self' parameter represent in a Python class method?",
                "option_a": "The class name",
                "option_b": "The instance of the class",
                "option_c": "A static variable",
                "option_d": "A global variable",
                "correct_option": "B",
                "explanation": "'self' refers to the instance of the class, allowing access to instance variables"
            },
            {
                "question_text": "Which method is called when an object is created in Python?",
                "option_a": "__start__",
                "option_b": "__create__",
                "option_c": "__init__",
                "option_d": "__new__",
                "correct_option": "C",
                "explanation": "__init__ is the constructor method called when creating an instance"
            },
            {
                "question_text": "What is the output of: print('Hello' * 3)?",
                "option_a": "Hello Hello Hello",
                "option_b": "HelloHelloHello",
                "option_c": "Hello 3",
                "option_d": "Error",
                "correct_option": "B",
                "explanation": "String multiplication repeats the string without spaces"
            },
            {
                "question_text": "Which data structure uses LIFO (Last In, First Out)?",
                "option_a": "Queue",
                "option_b": "Stack",
                "option_c": "List",
                "option_d": "Dictionary",
                "correct_option": "B",
                "explanation": "Stack follows LIFO principle - last element added is first to be removed"
            },
            {
                "question_text": "What does JSON stand for?",
                "option_a": "JavaScript Object Notation",
                "option_b": "Java Standard Object Notation",
                "option_c": "JavaScript Oriented Notation",
                "option_d": "Java Serialized Object Notation",
                "correct_option": "A",
                "explanation": "JSON stands for JavaScript Object Notation, a lightweight data format"
            },
            {
                "question_text": "Which exception is raised when dividing by zero in Python?",
                "option_a": "ValueError",
                "option_b": "TypeError",
                "option_c": "ZeroDivisionError",
                "option_d": "ArithmeticError",
                "correct_option": "C",
                "explanation": "ZeroDivisionError is specifically raised for division by zero operations"
            }
        ]
        
        for i, q_data in enumerate(questions, 1):
            question = MCQQuestion(
                exam_id=exam_id,
                **q_data
            )
            session.add(question)
            print(f"   ✅ Created question {i}: {q_data['question_text'][:50]}...")
        
        session.commit()
        print(f"\n✅ Successfully created {len(questions)} questions!")


if __name__ == "__main__":
    print("=" * 60)
    print("Creating Sample Exam Data")
    print("=" * 60)
    print()
    
    exam_id = create_sample_exam()
    print()
    create_sample_questions(exam_id)
    
    print()
    print("=" * 60)
    print("✨ Sample data created successfully!")
    print("=" * 60)
    print()
    print(f"📝 Access exam start page at:")
    print(f"   http://localhost:8000/exam/start/{exam_id}")
    print()
    print(f"📋 Manage questions at:")
    print(f"   http://localhost:8000/questions/?exam_id={exam_id}")
    print()
