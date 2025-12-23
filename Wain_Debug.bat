@echo off
cd /d "%~dp0"

REM ========================================
REM  Wain Debug Launcher - Console Visible
REM ========================================

echo.
echo ========================================
echo  Wain Debug Mode - Console Output
echo ========================================
echo.
echo Python version:
python --version
echo.
echo Starting Wain with full console output...
echo Press Ctrl+C to stop
echo.
echo ========================================
echo.

python -m wain

echo.
echo ========================================
echo Wain exited. Press any key to close...
pause >nul
