#!/bin/bash
# Quick Start Script for Online Exam System - Sprint 1

echo "========================================"
echo "Online Exam System - Sprint 1"
echo "Quick Start Script"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo ""

# Seed database
echo "Seeding database with sample data..."
python seed_data.py
echo ""

# Start server
echo "========================================"
echo "Starting FastAPI server..."
echo "========================================"
echo ""
echo "Server will start at: http://127.0.0.1:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn app.main:app --reload
