def test_smoke_true():
    """A trivial test to ensure pytest is discovering tests."""
    assert True


def test_app_importable():
    """Import the FastAPI app module to ensure it can be imported without errors."""
    import importlib
    import sys
    from pathlib import Path

    # Ensure the package root (online_exam_fastapi) is on sys.path so 'app' is importable
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    mod = importlib.import_module("app.main")
    assert hasattr(mod, "app")
