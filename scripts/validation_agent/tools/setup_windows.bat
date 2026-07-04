@echo off
REM DataBossX Validation Agent - Windows setup launcher.
setlocal
set "AGENT_ROOT=%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo Setup reported a blocker. See messages above.
  pause
  exit /b %ERRORLEVEL%
)
echo Setup finished.
pause
