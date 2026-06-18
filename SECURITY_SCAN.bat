@echo off
REM Run the DataBossX security scan (dependency audits + secret hygiene).
cd /d "%~dp0"
python scripts\security_scan.py
pause
