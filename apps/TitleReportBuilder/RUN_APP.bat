@echo off
REM ── Title Report Builder — launcher (self-setting-up on first run) ───────────
setlocal
cd /d "%~dp0"

REM 1) locate Python
set PY=
for %%P in (py python) do (
  %%P -3 --version >nul 2>&1 && set PY=%%P -3 && goto :havepy
  %%P --version  >nul 2>&1 && set PY=%%P     && goto :havepy
)
echo [ERROR] Python 3.11+ was not found.
echo Install it from https://www.python.org/downloads/ (check "Add to PATH"), then re-run.
pause & exit /b 1
:havepy

REM 2) create venv on first run
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv .venv || (echo [ERROR] venv creation failed & pause & exit /b 1)
)

REM 3) install / repair dependencies
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt || (echo [ERROR] dependency install failed & pause & exit /b 1)

REM 4) warn if LibreOffice (recalc) not found
where soffice >nul 2>&1 || echo [warn] LibreOffice (soffice) not found - recalc verification will be skipped.

REM 5) launch the Streamlit UI
echo Launching Title Report Builder...
python -m streamlit run title_report_builder\app.py
endlocal
