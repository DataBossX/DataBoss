@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
set "PID_FILE=%CD%\.runtime\databoss-title-intelligence.pid"
if not exist "%PID_FILE%" (
  echo ERROR: Start DataBoss Title Intelligence first.
  exit /b 2
)
set /p RECORDED_PID=<"%PID_FILE%"
set "DATABOSS_APP_PATH=%CD%\databoss_title_factory\app.py"
powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $env:RECORDED_PID) -ErrorAction SilentlyContinue; $app=[regex]::Escape($env:DATABOSS_APP_PATH); if($p -and (($p.CommandLine -match 'databoss_title_factory.+serve') -or ($p.CommandLine -match 'streamlit' -and $p.CommandLine -match $app))){exit 0}else{exit 1}" >nul 2>nul || (
  echo ERROR: The recorded DataBoss process is not running.
  exit /b 2
)
start "" "http://127.0.0.1:8501"
exit /b 0
