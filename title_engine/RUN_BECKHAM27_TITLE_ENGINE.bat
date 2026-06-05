@echo off
:: DataBoss Title Engine launcher for Windows
:: Section 27-11N-25W, Beckham County, Oklahoma

setlocal

:: ── Move to the title_engine directory ────────────────────────────────────────
cd /d "%~dp0"

:: ── Check Python ─────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

:: ── Create .env if missing ────────────────────────────────────────────────────
if not exist ".env" (
    echo No .env file found. Copying .env.example ...
    copy ".env.example" ".env"
    echo.
    echo IMPORTANT: Open .env in a text editor and add your OKCOUNTYRECORDS_API_KEY
    echo before using the app.
    echo.
    notepad .env
)

:: ── Install / upgrade dependencies ───────────────────────────────────────────
echo Installing Python dependencies...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo WARNING: Some packages may have failed to install. Continuing anyway...
)

:: ── Launch Streamlit ──────────────────────────────────────────────────────────
echo.
echo Starting DataBoss Title Engine...
echo Open your browser at: http://localhost:8502
echo Press Ctrl+C to stop.
echo.

streamlit run app.py --server.port 8502 --server.headless false

pause
