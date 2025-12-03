@echo off
REM DataBossX Command Center Launcher v9
REM This batch file launches the Streamlit dashboard

echo.
echo ==========================================
echo   DataBossX Command Center Launcher v9
echo ==========================================
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Check if we're in the right directory
if not exist databossx_dashboard9.py (
    echo ERROR: databossx_dashboard9.py not found!
    echo Please ensure this batch file is in the DataBossX root directory.
    pause
    exit /b 1
)

REM Try to activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo WARNING: No virtual environment found. Using system Python.
    echo.
)

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Check if Streamlit is installed
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo Streamlit not found. Installing required packages...
    python -m pip install streamlit pandas pillow --quiet
    if errorlevel 1 (
        echo ERROR: Failed to install required packages!
        pause
        exit /b 1
    )
)

REM Launch Streamlit
echo.
echo Starting DataBossX Command Center...
echo.
echo The dashboard will open in your default browser.
echo Press Ctrl+C to stop the server.
echo.

streamlit run databossx_dashboard9.py --server.port 8501 --server.headless false

REM If streamlit exits, pause so user can see any errors
if errorlevel 1 (
    echo.
    echo ERROR: Streamlit exited with an error!
    pause
)
