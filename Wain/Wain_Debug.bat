@echo off
cd /d "%~dp0"
echo.
echo ========================================
echo  Wain Debug Mode
echo ========================================
echo.
echo Checking Python...
python --version
echo.
echo Checking dependencies...
python -c "import nicegui; print('nicegui:', nicegui.__version__)"
python -c "import webview; print('webview:', webview.__version__)"
python -c "import PyQt6; print('PyQt6: OK')"
echo.
echo Starting Wain with full output...
echo ========================================
echo.
python wain.py
echo.
echo ========================================
echo App exited with code: %errorlevel%
echo ========================================
pause
