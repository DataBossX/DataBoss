@echo off
REM DataBossX Validation Agent - Windows setup (batch wrapper)
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"
echo == DataBossX Validation Agent setup ==

where powershell >nul 2>&1
if %ERRORLEVEL%==0 (
    powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0setup_windows.ps1"
    goto :done
)

REM Fallback: no PowerShell available.
where py >nul 2>&1
if %ERRORLEVEL%==0 ( set "PYCMD=py -3" ) else ( set "PYCMD=python" )

%PYCMD% --version >nul 2>&1
if not %ERRORLEVEL%==0 (
    echo BLOCKER: Python 3.11+ not found. Install Python 3.12 and re-run.
    goto :done
)

if not exist ".venv" ( %PYCMD% -m venv .venv )
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
if not exist ".env" if exist ".env.example" copy ".env.example" ".env"
python tools\healthcheck.py

:done
popd
endlocal
