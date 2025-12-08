@echo off
cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not in PATH
    echo.
    pause
    exit /b 1
)

REM Check if we should run installer
if "%1"=="--install" goto :install
if "%1"=="--debug" goto :debug

REM Try to run directly if dependencies are installed
REM Check ALL required packages including WebEngine and qtpy
python -c "import nicegui; import webview; import PyQt6; from PyQt6 import QtWebEngineWidgets; import qtpy" >nul 2>&1
if errorlevel 1 goto :install

REM Dependencies installed - launch with splash screen
REM Use pythonw with .pyw file for no console window
if exist "%~dp0wain_launcher.pyw" (
    start "" pythonw "%~dp0wain_launcher.pyw"
) else (
    REM Fallback to wain.py directly if launcher doesn't exist
    start "" pythonw "%~dp0wain.py"
)
exit

:install
REM Run the full installer/launcher (needs console for progress)
echo Installing dependencies...
python launch_wain.py %*
if errorlevel 1 (
    echo.
    echo An error occurred during installation.
    pause
)
exit

:debug
REM Debug mode - shows all output, keeps console open
echo Running in debug mode...
python wain.py
echo.
echo App exited. Press any key to close...
pause >nul
