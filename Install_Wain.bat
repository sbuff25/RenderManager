@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM ========================================
REM  Wain - First-Time Installer
REM  https://github.com/Spencer-Sliffe/Wain
REM ========================================

title Wain Installer

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║                    WAIN INSTALLER                        ║
echo  ║                                                          ║
echo  ║          Multi-Engine Render Queue Manager               ║
echo  ║                                                          ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

REM ========================================
REM  Step 1: Check Python Installation
REM ========================================
echo  [1/4] Checking Python installation...
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  ╔══════════════════════════════════════════════════════════╗
    echo  ║  ERROR: Python is not installed or not in PATH           ║
    echo  ╠══════════════════════════════════════════════════════════╣
    echo  ║                                                          ║
    echo  ║  Please install Python 3.10 or higher from:              ║
    echo  ║  https://www.python.org/downloads/                       ║
    echo  ║                                                          ║
    echo  ║  IMPORTANT: Check "Add Python to PATH" during install!   ║
    echo  ║                                                          ║
    echo  ╚══════════════════════════════════════════════════════════╝
    echo.
    echo  Press any key to open the Python download page...
    pause >nul
    start https://www.python.org/downloads/
    exit /b 1
)

REM Get Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo        Found Python %PYTHON_VERSION%

REM Check Python version is 3.10+
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

if %PY_MAJOR% LSS 3 (
    echo        [X] Python 3.10+ required, found %PYTHON_VERSION%
    echo.
    echo  Please upgrade Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo        [X] Python 3.10+ required, found %PYTHON_VERSION%
    echo.
    echo  Please upgrade Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo        [OK] Python version compatible
echo.

REM ========================================
REM  Step 2: Upgrade pip
REM ========================================
echo  [2/4] Upgrading pip...
echo.

python -m pip install --upgrade pip >nul 2>&1
if errorlevel 1 (
    echo        [!] Could not upgrade pip, continuing anyway...
) else (
    echo        [OK] pip is up to date
)
echo.

REM ========================================
REM  Step 3: Install Dependencies
REM ========================================
echo  [3/4] Installing dependencies...
echo.
echo        This may take a few minutes on first install.
echo.

set INSTALL_FAILED=0

REM --- NiceGUI ---
echo        Installing nicegui...
python -m pip install nicegui --quiet
if errorlevel 1 (
    echo        [X] Failed to install nicegui
    set INSTALL_FAILED=1
) else (
    echo        [OK] nicegui
)

REM --- PyQt6 ---
echo        Installing PyQt6...
python -m pip install PyQt6 --quiet
if errorlevel 1 (
    echo        [X] Failed to install PyQt6
    set INSTALL_FAILED=1
) else (
    echo        [OK] PyQt6
)

REM --- PyQt6-WebEngine ---
echo        Installing PyQt6-WebEngine...
python -m pip install PyQt6-WebEngine --quiet
if errorlevel 1 (
    echo        [X] Failed to install PyQt6-WebEngine
    set INSTALL_FAILED=1
) else (
    echo        [OK] PyQt6-WebEngine
)

REM --- qtpy ---
echo        Installing qtpy...
python -m pip install qtpy --quiet
if errorlevel 1 (
    echo        [X] Failed to install qtpy
    set INSTALL_FAILED=1
) else (
    echo        [OK] qtpy
)

REM --- Pillow ---
echo        Installing Pillow...
python -m pip install Pillow --quiet
if errorlevel 1 (
    echo        [X] Failed to install Pillow
    set INSTALL_FAILED=1
) else (
    echo        [OK] Pillow
)

REM --- pywebview (special handling for Python 3.13+) ---
echo        Installing pywebview...
if %PY_MAJOR% EQU 3 if %PY_MINOR% GEQ 13 (
    python -m pip install pywebview --no-deps --quiet
    python -m pip install proxy-tools bottle --quiet
) else (
    python -m pip install pywebview --quiet
)
if errorlevel 1 (
    echo        [X] Failed to install pywebview
    set INSTALL_FAILED=1
) else (
    echo        [OK] pywebview
)

echo.

REM Check if any installs failed
if %INSTALL_FAILED% EQU 1 (
    echo  ╔══════════════════════════════════════════════════════════╗
    echo  ║  WARNING: Some packages failed to install                ║
    echo  ╠══════════════════════════════════════════════════════════╣
    echo  ║  Wain may not work correctly.                            ║
    echo  ║  Try running this installer again, or install manually:  ║
    echo  ║                                                          ║
    echo  ║  pip install nicegui PyQt6 PyQt6-WebEngine qtpy Pillow   ║
    echo  ║  pip install pywebview                                   ║
    echo  ╚══════════════════════════════════════════════════════════╝
    echo.
)

REM ========================================
REM  Step 4: Verify Installation
REM ========================================
echo  [4/4] Verifying installation...
echo.

set VERIFY_FAILED=0

python -c "import nicegui" >nul 2>&1
if errorlevel 1 (
    echo        [X] nicegui - NOT FOUND
    set VERIFY_FAILED=1
) else (
    echo        [OK] nicegui
)

python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo        [X] PyQt6 - NOT FOUND
    set VERIFY_FAILED=1
) else (
    echo        [OK] PyQt6
)

python -c "from PyQt6 import QtWebEngineWidgets" >nul 2>&1
if errorlevel 1 (
    echo        [X] PyQt6-WebEngine - NOT FOUND
    set VERIFY_FAILED=1
) else (
    echo        [OK] PyQt6-WebEngine
)

python -c "import qtpy" >nul 2>&1
if errorlevel 1 (
    echo        [X] qtpy - NOT FOUND
    set VERIFY_FAILED=1
) else (
    echo        [OK] qtpy
)

python -c "import webview" >nul 2>&1
if errorlevel 1 (
    echo        [X] pywebview - NOT FOUND
    set VERIFY_FAILED=1
) else (
    echo        [OK] pywebview
)

python -c "from PIL import Image" >nul 2>&1
if errorlevel 1 (
    echo        [X] Pillow - NOT FOUND
    set VERIFY_FAILED=1
) else (
    echo        [OK] Pillow
)

echo.

REM ========================================
REM  Installation Complete
REM ========================================
if %VERIFY_FAILED% EQU 0 (
    echo  ╔══════════════════════════════════════════════════════════╗
    echo  ║                                                          ║
    echo  ║            INSTALLATION SUCCESSFUL!                      ║
    echo  ║                                                          ║
    echo  ╠══════════════════════════════════════════════════════════╣
    echo  ║                                                          ║
    echo  ║  Wain is ready to use.                                   ║
    echo  ║                                                          ║
    echo  ║  To launch Wain:                                         ║
    echo  ║    - Double-click Wain.bat                               ║
    echo  ║    - Or run: python -m wain                              ║
    echo  ║                                                          ║
    echo  ╚══════════════════════════════════════════════════════════╝
    echo.
    
    set /p LAUNCH="  Would you like to launch Wain now? (Y/N): "
    if /i "!LAUNCH!"=="Y" (
        echo.
        echo  Starting Wain...
        start "" pythonw wain_launcher.pyw
    )
) else (
    echo  ╔══════════════════════════════════════════════════════════╗
    echo  ║                                                          ║
    echo  ║            INSTALLATION INCOMPLETE                       ║
    echo  ║                                                          ║
    echo  ╠══════════════════════════════════════════════════════════╣
    echo  ║                                                          ║
    echo  ║  Some dependencies could not be verified.                ║
    echo  ║  Please check the errors above and try again.            ║
    echo  ║                                                          ║
    echo  ║  For help, visit:                                        ║
    echo  ║  https://github.com/Spencer-Sliffe/Wain                  ║
    echo  ║                                                          ║
    echo  ╚══════════════════════════════════════════════════════════╝
)

echo.
echo  Press any key to exit...
pause >nul
exit /b %VERIFY_FAILED%
