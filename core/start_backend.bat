@echo off
REM ============================================================
REM ArchgenCAD Backend - Windows Startup Script
REM ============================================================
REM API keys are loaded from .env file automatically.
REM Make sure you have created .env from .env.example first:
REM   copy .env.example .env
REM   (then edit .env with your real API keys)
REM ============================================================

IF NOT EXIST ".env" (
    echo ERROR: .env file not found.
    echo Please copy .env.example to .env and fill in your API keys.
    echo   copy .env.example .env
    pause
    exit /b 1
)

IF NOT EXIST "clients.json" (
    echo ERROR: clients.json not found.
    echo Please copy clients.example.json to clients.json and add your users.
    echo   copy clients.example.json clients.json
    pause
    exit /b 1
)

REM Create required runtime directories
if not exist "generated_models" mkdir generated_models
if not exist "pending_review" mkdir pending_review
if not exist "generation_archive" mkdir generation_archive
if not exist "feedback" mkdir feedback

echo ==========================================
echo  Starting ArchgenCAD Backend
echo ==========================================
echo  API:    http://localhost:8000
echo  Docs:   http://localhost:8000/docs
echo ==========================================

python -m uvicorn main:app --host 0.0.0.0 --port 8000
