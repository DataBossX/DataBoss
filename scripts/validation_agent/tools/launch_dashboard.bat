@echo off
REM Launch the DataBossX validation dashboard.
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Run tools\setup_windows.bat first to create .venv and install dependencies.
    popd & endlocal & exit /b 1
)

call ".venv\Scripts\activate.bat"
python tools\healthcheck.py
echo Starting Streamlit dashboard at http://localhost:8501 ...
python -m streamlit run app\dashboard.py
popd
endlocal
