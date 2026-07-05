@echo off
REM ==========================================================================
REM  DataBossX Land Intelligence -- Command Center launcher (Windows)
REM  Double-click to install deps and open the command center in your browser.
REM ==========================================================================
setlocal
cd /d "%~dp0"

echo(
echo   DATABOSSX . LAND INTELLIGENCE -- COMMAND CENTER
echo   ------------------------------------------------
echo   Installing dependencies (first run only)...
echo(

py -m pip install -r command_center\requirements.txt
if errorlevel 1 (
    echo(
    echo   [!] Dependency install failed. Ensure Python 3.10+ is installed and on PATH.
    pause
    exit /b 1
)

echo(
echo   Launching the command center...  (Ctrl+C in this window to stop)
echo   Your browser will open at http://localhost:8501
echo(

py -m streamlit run command_center\app.py

pause
endlocal
