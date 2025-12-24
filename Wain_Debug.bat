@echo off
cd /d "%~dp0"

REM ========================================
REM  Wain Debug Launcher - Full Diagnostics
REM  Creates detailed vantage_debug_*.log
REM ========================================

echo.
echo ========================================
echo  Wain Debug Mode - FULL DIAGNOSTICS
echo ========================================
echo.
echo Python version:
python --version
echo.
echo Debug mode ENABLED:
echo  - Console output will show all Vantage actions
echo  - Detailed log saved to: vantage_debug_[timestamp].log
echo  - Window state dumps every 5 seconds
echo.
echo Press Ctrl+C to stop
echo.
echo ========================================
echo.

REM Enable Wain debug mode via environment variable
set WAIN_DEBUG=1

python -m wain

echo.
echo ========================================
echo.
echo Wain exited. 
echo.
echo Check for vantage_debug_*.log files in this folder
echo for detailed startup diagnostics.
echo.
echo Press any key to close...
pause >nul
