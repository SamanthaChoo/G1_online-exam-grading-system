def test_smoke_true():
    """A trivial test to ensure pytest is discovering tests."""
    assert True


def test_app_importable():
    """Import the FastAPI app module to ensure it can be imported without errors."""
    import importlib
    import sys
    from pathlib import Path
    import os

    # Ensure the package root (online_exam_fastapi) is on sys.path so 'app' is importable
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Ensure the `app/static` directory exists (the application mounts it at import time).
    # Creating it here prevents import-time errors in CI environments where the directory
    # may not be present (static assets often aren't checked into the tests runner).
    static_dir = repo_root / "app" / "static"
    # Also create a top-level `app/static` (relative to repo root) — some branches
    # use a top-level `app/` package (the CI job linter/imports may expect that path).
    alt_static_dir = Path("app") / "static"
    try:
        os.makedirs(static_dir, exist_ok=True)
        os.makedirs(alt_static_dir, exist_ok=True)
    except Exception:
        # If we cannot create the directory for any reason, the import will surface the
        # original error which is useful for debugging; don't mask unexpected failures.
        pass

    mod = importlib.import_module("app.main")
    assert hasattr(mod, "app")
