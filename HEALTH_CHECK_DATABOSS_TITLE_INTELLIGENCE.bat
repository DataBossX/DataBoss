@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Run SETUP_DATABOSS_TITLE_INTELLIGENCE.bat first.
  exit /b 2
)
if not exist ".runtime\logs" mkdir ".runtime\logs" || exit /b 1
if defined DATABOSS_CONFIG (
  if not exist "%DATABOSS_CONFIG%" (
    echo ERROR: DATABOSS_CONFIG does not exist.
    exit /b 2
  )
  for %%I in ("%DATABOSS_CONFIG%") do set "CONFIG_ROOT=%%~dpI"
  ".venv\Scripts\python.exe" -m databoss_title_factory health --config "%DATABOSS_CONFIG%" --allow-root "%CONFIG_ROOT%" >>".runtime\logs\health-check.log" 2>&1
) else (
  ".venv\Scripts\python.exe" -m databoss_title_factory health >>".runtime\logs\health-check.log" 2>&1
)
set "RESULT=%ERRORLEVEL%"
type ".runtime\logs\health-check.log"
exit /b %RESULT%
