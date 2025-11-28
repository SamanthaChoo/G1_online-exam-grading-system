import sys
from pathlib import Path

import pytest
from sqlmodel import Session, text


def _ensure_app_on_path():
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root


@pytest.fixture(autouse=False)  # Changed to False - user must explicitly enable cleanup
def cleanup_db():
    """
    Clean up test data after each test.

    This keeps the shared SQLite DB from accumulating records across test runs,
    which is especially important when you're also using the same DB for
    manual testing via the UI.

    NOTE: This fixture is DISABLED by default (autouse=False) to prevent
    database resets during manual testing. To enable it for a specific test,
    add `@pytest.mark.usefixtures("cleanup_db")` to the test function or class.
    """
    _ensure_app_on_path()
    from app.database import engine

    yield  # run the test

    # Best-effort cleanup in FK-safe order.
    with Session(engine) as session:
        # Essay-related tables
        session.exec(text("DELETE FROM essayanswer"))
        session.exec(text("DELETE FROM examattempt"))
        session.exec(text("DELETE FROM examquestion"))

        # Core exam & enrollment tables
        session.exec(text("DELETE FROM exam"))
        session.exec(text("DELETE FROM enrollment"))
        session.exec(text("DELETE FROM courselecturer"))
        session.exec(text("DELETE FROM course"))

        # User & student tables
        session.exec(text("DELETE FROM student"))
        session.exec(text("DELETE FROM user"))

        # Auth-related
        session.exec(text("DELETE FROM passwordresettoken"))

        session.commit()


