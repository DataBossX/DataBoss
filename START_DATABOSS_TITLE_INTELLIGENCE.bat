@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Run SETUP_DATABOSS_TITLE_INTELLIGENCE.bat first.
  exit /b 2
)
if not exist ".runtime\logs" mkdir ".runtime\logs" || exit /b 1
if not defined DATABOSS_AUTH_DB set "DATABOSS_AUTH_DB=%CD%\.runtime\databoss_auth.sqlite3"
if not exist "%DATABOSS_AUTH_DB%" (
  echo ERROR: DATABOSS_AUTH_DB does not exist: "%DATABOSS_AUTH_DB%"
  echo Initialize it with the documented auth CLI before starting.
  exit /b 2
)
set "PID_FILE=%CD%\.runtime\databoss-title-intelligence.pid"
set "DATABOSS_APP_PATH=%CD%\databoss_title_factory\app.py"
if exist "%PID_FILE%" (
  set /p EXISTING_PID=<"%PID_FILE%"
  powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $env:EXISTING_PID) -ErrorAction SilentlyContinue; $app=[regex]::Escape($env:DATABOSS_APP_PATH); if($p -and (($p.CommandLine -match 'databoss_title_factory.+serve') -or ($p.CommandLine -match 'streamlit' -and $p.CommandLine -match $app))){exit 0}else{exit 1}" >nul 2>nul
  if not errorlevel 1 (
    echo DataBoss Title Intelligence is already running as PID !EXISTING_PID!.
    exit /b 0
  )
  del /q "%PID_FILE%" >nul 2>nul
)
powershell -NoProfile -Command "$app=[regex]::Escape($env:DATABOSS_APP_PATH); $p=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -match 'streamlit' -and $_.CommandLine -match $app} | Select-Object -First 1; if($p){Write-Error ('Matching DataBoss app already runs as PID ' + $p.ProcessId); exit 1}" >nul 2>nul || (
  echo ERROR: A matching DataBoss app is already running without the expected PID record.
  exit /b 2
)
for %%I in ("%DATABOSS_AUTH_DB%") do set "DATABOSS_ALLOW_ROOT=%%~dpI"
powershell -NoProfile -Command "$p=Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList @('-m','databoss_title_factory','serve','--auth-database',$env:DATABOSS_AUTH_DB,'--allow-root',$env:DATABOSS_ALLOW_ROOT,'--port','8501') -WorkingDirectory $PWD -RedirectStandardOutput '.runtime\logs\app.stdout.log' -RedirectStandardError '.runtime\logs\app.stderr.log' -PassThru; $p.Id | Set-Content -Encoding ascii '.runtime\databoss-title-intelligence.pid'; Start-Sleep -Seconds 2; if($p.HasExited){exit 1}" || (
  del /q "%PID_FILE%" >nul 2>nul
  echo ERROR: Application failed to start. Review .runtime\logs\app.stderr.log.
  exit /b 1
)
echo Started on http://127.0.0.1:8501 using the PID recorded in "%PID_FILE%".
exit /b 0
