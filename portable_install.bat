@echo off
setlocal
REM ============================================================================
REM Wain Portable Installer (no Inno Setup, no admin rights needed)
REM ============================================================================
REM Copies this folder to %LOCALAPPDATA%\Programs\Wain and creates Start-menu
REM shortcuts, so Wain behaves like a normally installed application.
REM User data (settings, job database, logs) lives in %APPDATA%\Wain.
REM
REM https://github.com/sbuff25/RenderManager
REM ============================================================================

set "SRC=%~dp0"
set "DEST=%LOCALAPPDATA%\Programs\Wain"

echo.
echo ============================================
echo  Wain Setup
echo ============================================
echo  Installing to: %DEST%
echo.

if not exist "%SRC%Wain.exe" (
    echo [X] Wain.exe not found next to this script.
    echo     Run this from inside the unzipped Wain folder.
    pause
    exit /b 1
)

robocopy "%SRC%." "%DEST%" /E /XF portable_install.bat portable_uninstall.bat >nul
if errorlevel 8 (
    echo [X] Copy failed. Close Wain if it is running and try again.
    pause
    exit /b 1
)
robocopy "%SRC%." "%DEST%" portable_uninstall.bat >nul

REM --- Start-menu shortcuts (per-user, no admin) ---
powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell;" ^
    "$p = [Environment]::GetFolderPath('Programs');" ^
    "$s = $ws.CreateShortcut($p + '\Wain.lnk');" ^
    "$s.TargetPath = '%DEST%\Wain.exe'; $s.WorkingDirectory = '%DEST%'; $s.IconLocation = '%DEST%\Wain.exe'; $s.Save();" ^
    "$w = $ws.CreateShortcut($p + '\Wain Worker (render node).lnk');" ^
    "$w.TargetPath = '%DEST%\Wain.exe'; $w.Arguments = '--worker'; $w.WorkingDirectory = '%DEST%'; $w.IconLocation = '%DEST%\Wain.exe'; $w.Save()"

choice /C YN /M "Create a desktop shortcut"
if not errorlevel 2 (
    powershell -NoProfile -Command ^
        "$ws = New-Object -ComObject WScript.Shell;" ^
        "$s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Wain.lnk');" ^
        "$s.TargetPath = '%DEST%\Wain.exe'; $s.WorkingDirectory = '%DEST%'; $s.IconLocation = '%DEST%\Wain.exe'; $s.Save()"
)

echo.
echo ============================================
echo  Wain installed!
echo ============================================
echo  - Launch from the Start menu: "Wain"
echo  - Render node mode: "Wain Worker (render node)"
echo  - Uninstall: run portable_uninstall.bat in %DEST%
echo.
choice /C YN /M "Launch Wain now"
if not errorlevel 2 start "" "%DEST%\Wain.exe"
endlocal
