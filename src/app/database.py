"""
Database configuration and initialization
Handles SQLite database connection using SQLModel
"""

from sqlmodel import SQLModel, create_engine, Session
from typing import Generator

# SQLite database URL
DATABASE_URL = "sqlite:///./exam_system.db"

# Create engine with SQLite
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    connect_args={"check_same_thread": False}  # Needed for SQLite
)


def init_db():
    """
    Initialize database - create all tables
    Called on application startup
    """
    from app.models import Exam, MCQQuestion, StudentAnswer, ExamResult
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """
    Dependency for getting database session
    Usage: session: Session = Depends(get_session)
    """
    with Session(engine) as session:
        yield session


def create_test_engine(database_url: str = "sqlite:///:memory:"):
    """
    Create a test-only SQLModel engine (in-memory by default).
    Call `set_engine` with the returned engine so the app uses it during tests.
    """
    from sqlmodel import create_engine as _create_engine
    # Use StaticPool so an in-memory SQLite database remains accessible
    # across multiple connections/threads (TestClient + app threads).
    from sqlalchemy.pool import StaticPool

    return _create_engine(
        database_url,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def set_engine(new_engine):
    """Replace the module-level engine with `new_engine`.

    Useful for tests that want to swap in an in-memory SQLite engine.
    """
    global engine
    engine = new_engine


def reset_db():
    """Drop and recreate all tables on the current engine.

    Use in tests to ensure a clean schema state.
    """
    # Ensure models are imported so metadata is populated
    from app.models import Exam, MCQQuestion, StudentAnswer, ExamResult  # noqa: F401

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
