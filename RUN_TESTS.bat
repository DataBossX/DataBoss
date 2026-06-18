@echo off
REM Run all DataBossX tests, lint and checks.
cd /d "%~dp0"
python scripts\test_all.py
pause
