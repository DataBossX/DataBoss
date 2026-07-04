@echo off
REM DataBossX Validation Agent desktop launcher.
REM
REM This file is the Desktop launcher fallback. Because the agent was built in a
REM cloud/repo environment with no access to your Windows Desktop, it was placed
REM here. To install it on your Desktop, run (on your Windows machine):
REM     powershell -ExecutionPolicy Bypass -File tools\create_desktop_launcher.ps1
REM
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Dependencies missing. Open a terminal in:
    echo   %AGENT_ROOT%
    echo and run: tools\setup_windows.bat
    pause
    popd & endlocal & exit /b 1
)

call ".venv\Scripts\activate.bat"
python tools\healthcheck.py
python -m core.launcher_log
start "" http://localhost:8501
python -m streamlit run app\dashboard.py
popd
endlocal
