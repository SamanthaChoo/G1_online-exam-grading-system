"""
Database configuration and session management
Uses SQLModel with SQLite for Sprint 1
Sprint 2: Migrate to PostgreSQL for production
"""

from sqlmodel import SQLModel, Session, create_engine
from typing import Generator

# SQLite database URL
# Sprint 2: Replace with PostgreSQL connection string
DATABASE_URL = "sqlite:///./exam_system.db"

# Create engine with check_same_thread=False for SQLite
# Sprint 2: Remove check_same_thread when migrating to PostgreSQL
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    connect_args={"check_same_thread": False}
)


def create_db_and_tables():
    """
    Create all database tables on application startup.
    Called from main.py startup event.
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    Used with FastAPI Depends() for automatic session management.
    
    Usage in routes:
        @router.get("/example")
        def example(session: Session = Depends(get_session)):
            # Use session here
            pass
    
    Sprint 2: Add connection pooling, read replicas
    """
    with Session(engine) as session:
        yield session
