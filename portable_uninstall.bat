@echo off
setlocal
REM ============================================================================
REM Wain Portable Uninstaller
REM ============================================================================
REM Removes the app folder and shortcuts created by portable_install.bat.
REM User data in %APPDATA%\Wain (settings, job history, logs) is kept —
REM delete that folder manually if you want a complete wipe.
REM ============================================================================

set "DEST=%LOCALAPPDATA%\Programs\Wain"

echo Uninstalling Wain from %DEST% ...

REM Remove shortcuts
powershell -NoProfile -Command ^
    "$p = [Environment]::GetFolderPath('Programs');" ^
    "Remove-Item -Force -ErrorAction SilentlyContinue ($p + '\Wain.lnk'), ($p + '\Wain Worker (render node).lnk'), ([Environment]::GetFolderPath('Desktop') + '\Wain.lnk')"

echo Shortcuts removed. Removing application files...
echo (Your settings and render history in %%APPDATA%%\Wain are kept.)

REM This script lives inside the folder being deleted — hand the final
REM removal to a detached cmd so the folder isn't locked by this process.
start "" /min cmd /c "timeout /t 2 /nobreak >nul & rmdir /s /q ""%DEST%"""
echo Done. The Wain folder will disappear in a moment.
timeout /t 3 >nul
endlocal
