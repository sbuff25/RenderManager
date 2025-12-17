@echo off
cd /d "%~dp0"

REM ========================================
REM  Wain - Render Queue Manager Launcher
REM  https://github.com/Spencer-Sliffe/Wain
REM ========================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not in PATH
    echo.
    echo  Please install Python 3.10 or higher from:
    echo  https://www.python.org/downloads/
    echo.
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Check command line arguments
if "%1"=="--install" goto :install
if "%1"=="--debug" goto :debug
if "%1"=="--help" goto :help

REM Check if all required packages are installed (including pywinauto for Vantage)
python -c "import nicegui; import webview; import PyQt6; from PyQt6 import QtWebEngineWidgets; import qtpy; from PIL import Image; import pywinauto" >nul 2>&1
if errorlevel 1 goto :install

REM Dependencies installed - launch Wain with splash screen (no console window)
echo Starting Wain...
start "" pythonw wain_launcher.pyw
exit

:install
REM Run with console to show installation progress
echo.
echo ========================================
echo  Wain - Installing Dependencies
echo ========================================
echo.
python -m wain
if errorlevel 1 (
    echo.
    echo An error occurred. Press any key to exit...
    pause >nul
)
exit

:debug
REM Debug mode - shows all output, keeps console open
echo.
echo ========================================
echo  Wain - Debug Mode
echo ========================================
echo.
echo Python version:
python --version
echo.
echo Checking dependencies...
python -c "import nicegui; print('nicegui:', nicegui.__version__)"
python -c "import PyQt6; print('PyQt6: OK')"
python -c "from PyQt6 import QtWebEngineWidgets; print('PyQt6-WebEngine: OK')"
python -c "import qtpy; print('qtpy:', qtpy.__version__)"
python -c "import webview; print('pywebview: OK')"
python -c "from PIL import Image; print('Pillow: OK')"
python -c "import pywinauto; print('pywinauto: OK')"
echo.
echo Starting Wain in debug mode...
echo ========================================
echo.
python -m wain
echo.
echo ========================================
echo Wain exited. Press any key to close...
pause >nul
exit

:help
echo.
echo ========================================
echo  Wain - Render Queue Manager
echo  https://github.com/Spencer-Sliffe/Wain
echo ========================================
echo.
echo Usage:
echo   Wain.bat            Launch Wain (installs deps if needed)
echo   Wain.bat --debug    Run with console output for debugging
echo   Wain.bat --install  Force reinstall dependencies
echo   Wain.bat --help     Show this help message
echo.
echo Requirements:
echo   - Python 3.10 or higher
echo   - Windows 10/11
echo.
pause
exit
