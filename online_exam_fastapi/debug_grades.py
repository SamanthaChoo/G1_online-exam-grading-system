from app.database import engine, create_db_and_tables
from sqlmodel import Session, select
from app.models import User, Student, ExamAttempt, Exam, EssayAnswer, ExamQuestion, MCQResult

create_db_and_tables()

session = Session(engine)

# Get student user
student_user = session.exec(select(User).where(User.role == 'student')).first()
if not student_user:
    print("No student user found")
    session.close()
    exit(1)

print(f'Student user: {student_user.id} - {student_user.name} (student_id: {student_user.student_id})')

if student_user.student_id:
    student_id = student_user.student_id
    
    # Get their attempts
    attempts = session.exec(select(ExamAttempt).where(ExamAttempt.student_id == student_id)).all()
    print(f'Essay attempts: {len(attempts)}')
    
    for att in attempts:
        exam = session.get(Exam, att.exam_id)
        exam_title = exam.title if exam else "NO EXAM FOUND"
        print(f'  Attempt {att.id}: Exam {att.exam_id} - {exam_title}')
        
        # Get answers
        answers = session.exec(select(EssayAnswer).where(EssayAnswer.attempt_id == att.id)).all()
        print(f'    Answers: {len(answers)}')
        
        # Get questions
        questions = session.exec(select(ExamQuestion).where(ExamQuestion.exam_id == att.exam_id)).all()
        print(f'    Questions: {len(questions)}')
    
    # Get MCQ results
    mcq_results = session.exec(select(MCQResult).where(MCQResult.student_id == student_id)).all()
    print(f'MCQ results: {len(mcq_results)}')
    
    for mcq in mcq_results:
        exam = session.get(Exam, mcq.exam_id)
        exam_title = exam.title if exam else "NO EXAM FOUND"
        print(f'  MCQResult {mcq.id}: Exam {mcq.exam_id} - {exam_title} - Score: {mcq.score}/{mcq.total_questions}')

session.close()
