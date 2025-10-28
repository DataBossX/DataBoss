@echo off
python -m pip install -U pip
pip install -r requirements.txt
python -m playwright install chromium
set PYTHONIOENCODING=utf-8
python automation\playwright_bot.py
pause
