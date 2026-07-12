@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
if not exist "databoss_title_factory\pyproject.toml" (
  echo ERROR: Run this launcher from the repository root.
  exit /b 2
)
where py >nul 2>nul || (
  echo ERROR: Python launcher "py" is required.
  exit /b 2
)
if not exist ".runtime\logs" mkdir ".runtime\logs" || exit /b 1
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv ".venv" >>".runtime\logs\setup.log" 2>&1 || exit /b 1
".venv\Scripts\python.exe" -m pip install --upgrade pip >>".runtime\logs\setup.log" 2>&1 || exit /b 1
".venv\Scripts\python.exe" -m pip install -e "databoss_title_factory" >>".runtime\logs\setup.log" 2>&1 || exit /b 1
".venv\Scripts\python.exe" -m databoss_title_factory health >>".runtime\logs\setup.log" 2>&1 || exit /b 1
echo Setup complete. Review .runtime\logs\setup.log.
exit /b 0
