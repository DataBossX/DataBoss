@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Run SETUP_DATABOSS_TITLE_INTELLIGENCE.bat first.
  exit /b 2
)
if not defined DATABOSS_PROJECT_ROOT (
  echo ERROR: Set DATABOSS_PROJECT_ROOT to the mounted evidence folder.
  exit /b 2
)
if not exist "%DATABOSS_PROJECT_ROOT%\" (
  echo ERROR: DATABOSS_PROJECT_ROOT is not an existing directory.
  exit /b 2
)
if not exist ".runtime\logs" mkdir ".runtime\logs" || exit /b 1
".venv\Scripts\python.exe" -m databoss_title_factory inventory --root "%DATABOSS_PROJECT_ROOT%" --allow-root "%DATABOSS_PROJECT_ROOT%" >>".runtime\logs\source-inventory.log" 2>&1
exit /b %ERRORLEVEL%
