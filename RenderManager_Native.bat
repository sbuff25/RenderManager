@echo off
title Render Manager (Desktop App)
cd /d "%~dp0"
echo Starting Render Manager (Desktop Mode)...
echo Using NiceGUI with PyQt6 backend - no browser needed!
echo.
python render_manager_ITT04_native.py
pause
