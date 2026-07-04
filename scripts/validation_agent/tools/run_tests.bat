@echo off
REM DataBossX Validation Agent - run the test suite with coverage
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"
set "VPY=%AGENT_ROOT%\.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo BLOCKER: .venv missing. Run tools\setup_windows.bat first.
  popd & endlocal & exit /b 1
)
"%VPY%" -m pytest tests -v --cov=. --cov-report=term-missing
set RC=%ERRORLEVEL%
popd
endlocal & exit /b %RC%
