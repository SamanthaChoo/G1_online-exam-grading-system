@echo off
REM Helper to run flake8 against the FastAPI app using the repo .flake8 config
REM Usage: double-click or run from cmd in the repo root

SETLOCAL
REM Ensure script runs from repo root directory where this file lives
CD /D "%~dp0"

echo Running flake8 on online_exam_fastapi/app with .flake8 config
python -m flake8 online_exam_fastapi/app --config .flake8
IF %ERRORLEVEL% NEQ 0 (
  echo.
  echo flake8 found issues. Fix them locally or run format-code.bat to autoformat.
  exit /b %ERRORLEVEL%
)
echo No linter errors found.
ENDLOCAL
