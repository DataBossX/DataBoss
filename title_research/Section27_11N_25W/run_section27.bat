@echo off
REM Double-click launcher for the Section 27 local finish.
REM Runs the PowerShell pipeline with execution policy bypass for THIS process only.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_section27.ps1"
echo.
pause
