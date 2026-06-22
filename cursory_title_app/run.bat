@echo off
REM ============================================================
REM  Cursory Title App - one-click launcher (Windows)
REM ============================================================
setlocal
cd /d "%~dp0"

REM 1) venv
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat

REM 2) deps
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium

REM 3) env check
if not exist ".env" (
    echo.
    echo  WARNING: no .env found. Copy .env.example to .env and add your API key.
    echo.
)

REM 4) Reminder: start YOUR Chrome with remote debugging, then log in.
echo.
echo  Before using the browser features, start Chrome like this in another window:
echo     chrome.exe --remote-debugging-port=9222 --user-data-dir="%%LOCALAPPDATA%%\CTA\chrome"
echo  then log in to OKCountyRecords in that window.
echo.

set PYTHONIOENCODING=utf-8
streamlit run ui\app.py

pause
endlocal
