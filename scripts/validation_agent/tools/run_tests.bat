@echo off
setlocal
cd /d "%~dp0.."
call ".venv\Scripts\activate.bat"
python -m pytest tests -v --cov=. --cov-report=term-missing
pause
