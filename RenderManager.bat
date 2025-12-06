@echo off
title Render Manager ITT02
cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist ".venv" (
    echo First run - setting up environment...
    python -m pip install --upgrade pip >nul 2>&1
    python -m pip install Pillow >nul 2>&1
    echo Done!
    echo.
)

REM Run the application
python render_manager_ITT02.py

REM Keep window open if there was an error
if errorlevel 1 pause
