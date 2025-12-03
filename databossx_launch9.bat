@echo off
REM DataBossX Command Center Launcher
REM This batch file launches the Streamlit dashboard

echo ================================================
echo   DataBossX Command Center Launcher v9.0
echo ================================================
echo.

REM Navigate to the DataBossX root directory
REM For Windows, this should be I:\DataBossX_Final_Modular
REM Adjust the path below if your installation is elsewhere
cd /d I:\DataBossX_Final_Modular
echo Current directory: %CD%
echo.

REM Check if we're in the right directory
if not exist "databossx_dashboard9.py" (
    echo ERROR: Cannot find databossx_dashboard9.py
    echo Please ensure you're in the correct directory.
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

REM Activate the Python virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo WARNING: No virtual environment found.
    echo Using system Python...
)
echo.

REM Check if Streamlit is installed
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo ERROR: Streamlit is not installed!
    echo.
    echo Installing required packages...
    pip install streamlit pillow
    echo.
)

REM Launch the dashboard
echo Launching DataBossX Command Center...
echo.
echo ================================================
echo   Dashboard will open in your browser
echo   Press Ctrl+C to stop the server
echo ================================================
echo.

streamlit run databossx_dashboard9.py

REM If streamlit exits, pause so user can see any errors
echo.
echo ================================================
echo   Dashboard stopped
echo ================================================
echo.
pause
