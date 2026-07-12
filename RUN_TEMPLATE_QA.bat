@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Run SETUP_DATABOSS_TITLE_INTELLIGENCE.bat first.
  exit /b 2
)
if not defined DATABOSS_TEMPLATE_PATH (
  echo ERROR: Set DATABOSS_TEMPLATE_PATH to an existing .xlsx or .xlsm file.
  exit /b 2
)
if not exist "%DATABOSS_TEMPLATE_PATH%" (
  echo ERROR: DATABOSS_TEMPLATE_PATH does not exist.
  exit /b 2
)
for %%I in ("%DATABOSS_TEMPLATE_PATH%") do set "TEMPLATE_ROOT=%%~dpI"
if not exist ".runtime\logs" mkdir ".runtime\logs" || exit /b 1
".venv\Scripts\python.exe" -m databoss_title_factory template-qa --template "%DATABOSS_TEMPLATE_PATH%" --allow-root "%TEMPLATE_ROOT%" >>".runtime\logs\template-qa.log" 2>&1
exit /b %ERRORLEVEL%
