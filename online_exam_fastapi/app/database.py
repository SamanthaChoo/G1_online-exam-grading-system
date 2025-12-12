"""Database configuration and session dependency."""

from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///./online_exam.db"

# echo=False to avoid noisy logs; toggle for debugging
engine = create_engine(
    DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)


def create_db_and_tables() -> None:
    """Create database tables based on SQLModel metadata."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session
