@echo off
REM DataBossX Validation Agent - launch the Streamlit dashboard
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo .venv not found. Running setup first...
    call "%~dp0setup_windows.bat"
)

call ".venv\Scripts\activate.bat"

REM Load .env into the environment (KEY=VALUE lines, ignore comments).
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        set "line=%%A"
        if not "%%A"=="" if not "!line:~0,1!"=="#" set "%%A=%%B"
    )
)

echo Running healthcheck...
python tools\healthcheck.py

echo Starting dashboard at http://localhost:8501 ...
start "" "http://localhost:8501"
python -m streamlit run app\dashboard.py --server.headless true

popd
endlocal
