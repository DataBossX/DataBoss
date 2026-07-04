@echo off
REM DataBossX Validation Agent - Windows setup (batch wrapper)
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
    powershell -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
    goto :done
)

echo Python launcher not found. Attempting winget install of Python 3.12...
winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
powershell -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"

:done
popd
endlocal
