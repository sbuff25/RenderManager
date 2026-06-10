@echo off
setlocal enabledelayedexpansion
REM ============================================================================
REM Wain Installer Build Script (v2.20.0)
REM ============================================================================
REM Produces:
REM   dist\Wain\                          - PyInstaller onedir bundle
REM   dist\Wain-<version>-portable.zip    - portable build (render nodes)
REM   dist\installer\Wain-Setup-<version>.exe - Inno Setup installer
REM
REM Requirements:
REM   - Python 3.10+ on PATH (same one that runs Wain)
REM   - Inno Setup 6 for the installer step (https://jrsoftware.org/isinfo.php)
REM
REM https://github.com/sbuff25/RenderManager
REM ============================================================================

cd /d "%~dp0"

echo.
echo ============================================
echo  Wain Installer Build
echo ============================================

REM --- Read version from wain/config.py ---
REM (via temp file: for /f chokes on nested quotes/parens in python -c)
python -c "import re; s=open('wain/config.py', encoding='utf-8').read(); print(re.search(r'APP_VERSION = .([0-9.]+).', s).group(1))" > "%TEMP%\wain_version.txt"
if errorlevel 1 (
    echo [X] Could not read APP_VERSION from wain\config.py - is Python on PATH?
    exit /b 1
)
set /p VERSION=<"%TEMP%\wain_version.txt"
del "%TEMP%\wain_version.txt" >nul 2>&1
if "%VERSION%"=="" (
    echo [X] Could not read APP_VERSION from wain\config.py
    exit /b 1
)
echo  Version: %VERSION%
echo.

REM --- Ensure dependencies + PyInstaller ---
echo [1/4] Installing build dependencies...
python -m pip install --quiet --upgrade pyinstaller
python -m pip install --quiet nicegui PyQt6 PyQt6-WebEngine qtpy pywebview Pillow pywinauto
if errorlevel 1 (
    echo [X] Dependency installation failed
    exit /b 1
)

REM --- PyInstaller bundle ---
echo [2/4] Building PyInstaller bundle (this takes a few minutes)...
python -m PyInstaller wain.spec --noconfirm --clean
if errorlevel 1 (
    echo [X] PyInstaller build failed
    exit /b 1
)
if not exist "dist\Wain\Wain.exe" (
    echo [X] dist\Wain\Wain.exe not found after build
    exit /b 1
)

REM --- Portable zip ---
echo [3/4] Creating portable zip...
if exist "dist\Wain-%VERSION%-portable.zip" del "dist\Wain-%VERSION%-portable.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Wain' -DestinationPath 'dist\Wain-%VERSION%-portable.zip' -Force"
if errorlevel 1 (
    echo [!] Portable zip creation failed (continuing)
) else (
    echo     dist\Wain-%VERSION%-portable.zip
)

REM --- Inno Setup installer ---
echo [4/4] Building installer...
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
where ISCC >nul 2>&1 && set "ISCC=ISCC"

if "%ISCC%"=="" (
    echo [!] Inno Setup 6 not found - skipping installer.
    echo     Install from https://jrsoftware.org/isinfo.php then re-run,
    echo     or build manually: ISCC /DMyAppVersion=%VERSION% installer.iss
) else (
    "%ISCC%" /Q /DMyAppVersion=%VERSION% installer.iss
    if errorlevel 1 (
        echo [X] Installer build failed
        exit /b 1
    )
    echo     dist\installer\Wain-Setup-%VERSION%.exe
)

echo.
echo ============================================
echo  Build complete!
echo ============================================
echo  Test checklist:
echo    1. dist\Wain\Wain.exe launches, UI loads, version chip shows %VERSION%
echo    2. Add + render a Blender job (engine detection works frozen)
echo    3. Settings - enable network mode - check API token in log
echo    4. On another machine: portable zip - Wain.exe --worker (setup dialog)
echo    5. Install via setup exe, repeat 1-3, then uninstall cleanly
echo.
endlocal
