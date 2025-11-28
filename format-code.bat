@echo off
REM Helper to install formatting tools (user install), run isort and black on the FastAPI app,
REM then re-run flake8. Run this from the repo root.

SETLOCAL
CD /D "%~dp0"

echo Installing isort and black (user install)
python -m pip install --user isort black || (
  echo Failed to install isort/black. Install manually and re-run.
  exit /b 1
)

echo Running isort (organize imports) on online_exam_fastapi
python -m isort online_exam_fastapi || (
  echo isort failed; aborting.
  exit /b 1
)

echo Running black (code formatter) on online_exam_fastapi
python -m black online_exam_fastapi || (
  echo black failed; aborting.
  exit /b 1
)

echo Re-running flake8
python -m flake8 online_exam_fastapi/app --config .flake8
IF %ERRORLEVEL% NEQ 0 (
  echo.
  echo Lint still reports issues. Address remaining items (unused imports, E402, etc.) manually.
  exit /b %ERRORLEVEL%
)

echo Formatting complete and linting passed (or no new errors).
ENDLOCAL
