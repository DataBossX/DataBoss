@echo off
REM ==========================================================================
REM  DataBossX Land Intelligence - Windows launcher
REM  Finds Python, creates a venv, installs deps, launches Streamlit, opens
REM  the browser at http://localhost:8501.
REM ==========================================================================
setlocal
cd /d "%~dp0"

REM --- Locate a Python interpreter -----------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python 3 was not found on PATH.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    echo         and be sure to check "Add Python to PATH".
    pause
    exit /b 1
)

REM --- Create the virtual environment if missing ---------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment (.venv)...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

REM --- Install / update dependencies ---------------------------------------
echo [SETUP] Installing dependencies (first run can take a few minutes)...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. See messages above.
    pause
    exit /b 1
)

REM --- Ensure the template exists ------------------------------------------
if not exist "data\template\template.xlsx" (
    echo [SETUP] Generating data\template\template.xlsx...
    python make_template.py
)

REM --- Launch Streamlit and open the browser -------------------------------
echo [RUN] Launching DataBossX Land Intelligence at http://localhost:8501
start "" http://localhost:8501
python -m streamlit run app.py --server.port 8501

endlocal
