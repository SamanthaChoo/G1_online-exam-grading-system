from app.database import create_db_and_tables, engine
from sqlmodel import Session, select
from app.models import Exam, ExamQuestion

create_db_and_tables()

with Session(engine) as session:
    # Find orphan questions (exam_id is NULL or 0)
    stmt = select(ExamQuestion).where((ExamQuestion.exam_id == None) | (ExamQuestion.exam_id == 0))
    orphans = session.exec(stmt).all()
    if not orphans:
        print('No orphan questions found.')
    else:
        # Choose first exam as target
        exams = session.exec(select(Exam)).all()
        if not exams:
            print('No exams present to associate orphan questions with. Create an exam first.')
        else:
            target = exams[0]
            for q in orphans:
                print(f"Associating question id={q.id} -> exam id={target.id}")
                q.exam_id = target.id
                session.add(q)
            session.commit()
            print(f"Associated {len(orphans)} orphan question(s) to exam id={target.id} ({target.title})")
