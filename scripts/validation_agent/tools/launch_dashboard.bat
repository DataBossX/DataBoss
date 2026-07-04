@echo off
REM DataBossX Validation Agent - launch the Streamlit dashboard
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"
set "VPY=%AGENT_ROOT%\.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo .venv not found. Running setup first...
  call "%~dp0setup_windows.bat"
)
if not exist "%VPY%" (
  echo BLOCKER: virtual environment missing. Run tools\setup_windows.bat manually.
  popd & endlocal & exit /b 1
)
echo Running healthcheck...
"%VPY%" "%AGENT_ROOT%\tools\healthcheck.py"
echo Starting dashboard at http://localhost:8501 ...
start "" http://localhost:8501
"%VPY%" -m streamlit run "%AGENT_ROOT%\app\dashboard.py" --server.headless true
popd
endlocal
