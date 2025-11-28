@echo off
REM Quick Start Script for Online Exam System - Sprint 1

echo ========================================
echo Online Exam System - Sprint 1
echo Quick Start Script
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate
echo.

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
echo.

REM Seed database
echo Seeding database with sample data...
python seed_data.py
echo.

REM Start server
echo ========================================
echo Starting FastAPI server...
echo ========================================
echo.
echo Server will start at: http://127.0.0.1:8000
echo.
echo Press Ctrl+C to stop the server
echo.

uvicorn app.main:app --reload
