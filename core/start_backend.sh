#!/bin/bash
# ============================================================
# ArchgenCAD Backend — Linux/macOS Startup Script
# ============================================================
# Requirements:
#   - Python 3.10+
#   - FreeCAD installed (see SETUP.md for instructions)
#   - .env file configured (copy from .env.example)
#   - pip install -r requirements.txt
# ============================================================

set -e  # Exit on any error

# Check .env exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found."
    echo "Please copy .env.example to .env and fill in your API keys."
    echo "  cp .env.example .env"
    exit 1
fi

# Check clients.json exists  
if [ ! -f "clients.json" ]; then
    echo "ERROR: clients.json not found."
    echo "Please copy clients.example.json to clients.json and add your user(s)."
    echo "  cp clients.example.json clients.json"
    exit 1
fi

# Load environment variables from .env
export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)

# Create required runtime directories
mkdir -p generated_models
mkdir -p pending_review
mkdir -p generation_archive
mkdir -p feedback

echo "=========================================="
echo " Starting ArchgenCAD Backend"
echo "=========================================="
echo " API:       http://localhost:8000"
echo " Docs:      http://localhost:8000/docs"
echo " Health:    http://localhost:8000/health"
echo "=========================================="

# Start Uvicorn — no --reload flag to prevent FreeCAD DLL issues
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
