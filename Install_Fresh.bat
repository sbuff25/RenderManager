@echo off
cd /d "%~dp0"
echo.
echo ========================================
echo  Wain - Fresh Installation
echo ========================================
echo.
echo This will uninstall and reinstall all
echo dependencies in the correct order.
echo.
pause

echo.
echo [Step 1/6] Checking Python version...
python --version
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

echo.
echo [Step 2/6] Uninstalling old packages...
pip uninstall nicegui pywebview PyQt6 PyQt6-WebEngine PyQt6-Qt6 PyQt6-sip qtpy proxy-tools bottle pythonnet clr-loader -y 2>nul

echo.
echo [Step 3/6] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [Step 4/6] Installing PyQt6 and WebEngine (MUST be first)...
pip install PyQt6
if errorlevel 1 (
    echo ERROR: Failed to install PyQt6
    pause
    exit /b 1
)
pip install PyQt6-WebEngine
if errorlevel 1 (
    echo ERROR: Failed to install PyQt6-WebEngine
    pause
    exit /b 1
)
pip install qtpy
if errorlevel 1 (
    echo ERROR: Failed to install qtpy
    pause
    exit /b 1
)

echo.
echo [Step 5/6] Installing pywebview...
REM Check Python version for special handling
python -c "import sys; exit(0 if sys.version_info >= (3,13) else 1)" 2>nul
if errorlevel 1 (
    echo Python 3.10-3.12 detected - standard install
    pip install pywebview
) else (
    echo Python 3.13+ detected - installing without pythonnet
    pip install pywebview --no-deps
    pip install proxy-tools bottle
)
if errorlevel 1 (
    echo ERROR: Failed to install pywebview
    pause
    exit /b 1
)

echo.
echo [Step 6/7] Installing Pillow (image processing)...
pip install Pillow
if errorlevel 1 (
    echo ERROR: Failed to install Pillow
    pause
    exit /b 1
)

echo.
echo [Step 7/7] Installing NiceGUI (last)...
pip install nicegui
if errorlevel 1 (
    echo ERROR: Failed to install nicegui
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Installation Complete!
echo ========================================
echo.
echo Verifying installation...
echo.
python -c "import PyQt6; print('PyQt6: OK')"
python -c "from PyQt6 import QtWebEngineWidgets; print('PyQt6-WebEngine: OK')"
python -c "import webview; print('pywebview: OK')"
python -c "from PIL import Image; print('Pillow: OK')"
python -c "import nicegui; print('nicegui:', nicegui.__version__)"
echo.
echo Now run Test_Dependencies.bat to verify everything works.
echo.
pause
