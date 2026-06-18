@echo off
REM Report outdated dependencies (safe, report-only by default).
cd /d "%~dp0"
python scripts\update_deps_safe.py
pause
