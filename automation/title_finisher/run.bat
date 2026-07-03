@echo off
REM TitleFinisher launcher (Windows). Installs deps on first run, then dispatches.
setlocal
cd /d "%~dp0"

if not exist .venv (
  echo [setup] creating venv + installing requirements...
  python -m venv .venv
  call .venv\Scripts\python -m pip install -q --upgrade pip
  call .venv\Scripts\pip install -q -r requirements.txt
)
call .venv\Scripts\python -m titlefinisher %*
endlocal
