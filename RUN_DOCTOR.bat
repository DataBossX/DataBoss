@echo off
REM Check the DataBossX environment for common problems.
cd /d "%~dp0"
python scripts\doctor.py
pause
