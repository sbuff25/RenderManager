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

REM Try to run wain.py directly first (faster if already installed)
python -c "import nicegui, webview, PyQt6" >nul 2>&1
if errorlevel 1 goto :install

REM Dependencies installed, launch with pythonw (no console)
REM Use "start" to detach, then exit batch immediately
start "" pythonw "%~dp0wain.py"
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
