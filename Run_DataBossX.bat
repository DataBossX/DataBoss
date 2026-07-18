@echo off
setlocal
title DataBossX Command Center
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON=py"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo.
    echo DataBossX needs Python 3.11 or newer.
    echo Install Python from https://www.python.org/downloads/windows/
    echo Select "Add Python to PATH", then run this file again.
    pause
    exit /b 1
  )
  set "PYTHON=python"
)

if not exist ".venv-kernel\Scripts\python.exe" (
  echo Setting up DataBossX for the first time...
  %PYTHON% -m venv ".venv-kernel"
  if errorlevel 1 goto :failed
)

".venv-kernel\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements-kernel.txt
if errorlevel 1 goto :failed

echo.
echo Starting DataBossX. Your browser will open automatically.
echo Keep this window open while DataBossX is running.
echo Source documents and approved templates are never overwritten.
echo.
".venv-kernel\Scripts\python.exe" run_databossx.py serve --open
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo DataBossX could not start. No source documents were changed.
echo Copy the error above when asking for help.
pause
exit /b 1
