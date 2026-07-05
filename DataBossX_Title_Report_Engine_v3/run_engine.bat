@echo off
REM ==========================================================================
REM  DataBossX Title Report Engine v3  --  one-click runner (Windows)
REM  Section 31-12N-24W, Roger Mills County, Oklahoma
REM
REM  1. creates a venv if missing   2. installs requirements
REM  3. runs app.py                 4. prints final output path + QA status
REM  5. pauses so the window stays open
REM ==========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Horizon root = the folder that CONTAINS this engine folder (edit if needed).
set "HORIZON_ROOT=%~dp0.."

echo(
echo === DataBossX Title Report Engine v3 ===
echo Horizon root: %HORIZON_ROOT%
echo(

REM --- 1. venv ---------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [setup] creating virtual environment...
    py -3 -m venv .venv 2>nul || python -m venv .venv
)
set "PY=.venv\Scripts\python.exe"

REM --- 2. requirements ------------------------------------------------------
echo [setup] installing requirements...
"%PY%" -m pip install --upgrade pip >nul 2>&1
"%PY%" -m pip install -r requirements.txt

REM --- 3. run ----------------------------------------------------------------
echo(
echo [run] executing engine...
"%PY%" app.py --root "%HORIZON_ROOT%"
set "RC=%ERRORLEVEL%"

echo(
echo ==========================================================================
if "%RC%"=="0" (
    echo QA STATUS: PASS or PASS WITH REVIEW FLAGS
) else (
    echo QA STATUS: FAIL ^(exit code %RC%^) -- see logs\QA_VALIDATION_REPORT.xlsx
)
echo Final report:  %HORIZON_ROOT%\SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx
echo Logs:          %~dp0logs
echo Run summary:   %~dp0logs\RUN_SUMMARY.md
echo ==========================================================================
echo(
pause
endlocal
