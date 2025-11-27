import sys
import os
from pathlib import Path

# Ensure src is on sys.path so we can import the app module
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient
import pytest

from app.database import create_test_engine, set_engine, reset_db
from main import app


@pytest.fixture
def client():
    """Create a TestClient using an in-memory SQLite engine.

    This fixture resets the schema before each test so tests stay independent.
    """
    engine = create_test_engine()
    set_engine(engine)
    reset_db()

    with TestClient(app) as client:
        yield client


def test_home_returns_200(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200


def test_select_exam_page(client: TestClient) -> None:
    r = client.get("/questions/select_exam")
    assert r.status_code == 200
