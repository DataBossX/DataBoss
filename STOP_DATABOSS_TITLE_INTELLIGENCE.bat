@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
set "PID_FILE=%CD%\.runtime\databoss-title-intelligence.pid"
if not exist "%PID_FILE%" (
  echo No recorded DataBoss process is running.
  exit /b 0
)
set /p RECORDED_PID=<"%PID_FILE%"
set "DATABOSS_APP_PATH=%CD%\databoss_title_factory\app.py"
echo(%RECORDED_PID%| findstr /r "^[1-9][0-9]*$" >nul || (
  echo ERROR: Refusing to stop anything because the PID file is invalid.
  exit /b 2
)
powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $env:RECORDED_PID) -ErrorAction SilentlyContinue; if(-not $p){exit 3}; $app=[regex]::Escape($env:DATABOSS_APP_PATH); $matches=(($p.CommandLine -match 'databoss_title_factory.+serve') -or ($p.CommandLine -match 'streamlit' -and $p.CommandLine -match $app)); if(-not $matches){exit 4}; Stop-Process -Id ([int]$env:RECORDED_PID) -ErrorAction Stop" 
if errorlevel 4 (
  echo ERROR: Refusing to stop PID %RECORDED_PID%; it is not the recorded DataBoss serve command.
  exit /b 2
)
if errorlevel 3 (
  del /q "%PID_FILE%" >nul 2>nul
  echo Recorded process no longer exists; stale PID file removed.
  exit /b 0
)
if errorlevel 1 (
  echo ERROR: Could not stop recorded PID %RECORDED_PID%.
  exit /b 1
)
del /q "%PID_FILE%" >nul 2>nul
echo Stopped recorded DataBoss PID %RECORDED_PID%.
exit /b 0
