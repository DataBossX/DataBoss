@echo off
REM DataBossX Validation Agent - Windows setup launcher (delegates to PowerShell)
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"
echo == DataBossX Validation Agent setup ==
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
set RC=%ERRORLEVEL%
popd
if %RC% NEQ 0 (
  echo.
  echo Setup reported a blocker. See messages above.
) else (
  echo.
  echo Setup finished successfully.
)
endlocal & exit /b %RC%
