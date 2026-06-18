@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - INSTALL
REM Creates a local Python venv, installs dependencies, installs Playwright
REM Chromium, and creates working folders.
REM ============================================================================
setlocal
cd /d "%~dp0"

echo ============================================================
echo  HorizonTitleLinkExtractor - INSTALL
echo ============================================================

REM --- 1. Find Python ---------------------------------------------------------
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYLAUNCH=py -3.11"
) else (
    set "PYLAUNCH=python"
)

echo.
echo [1/5] Creating virtual environment (.venv) ...
%PYLAUNCH% -m venv .venv
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Could not create the virtual environment.
    echo Make sure Python 3.11+ is installed and on your PATH.
    pause
    exit /b 1
)

set "VENV_PY=.venv\Scripts\python.exe"

echo.
echo [2/5] Upgrading pip ...
"%VENV_PY%" -m pip install --upgrade pip

echo.
echo [3/5] Installing requirements ...
"%VENV_PY%" -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo [4/5] Installing Playwright Chromium ...
"%VENV_PY%" -m playwright install chromium

echo.
echo [5/5] Creating working folders ...
for %%D in (input output logs temp debug .auth) do (
    if not exist "%%D" mkdir "%%D"
)

echo.
echo ============================================================
echo  INSTALL COMPLETE
echo ============================================================
echo  NEXT STEPS:
echo   1. Copy .env.example to .env and add your API keys.
echo   2. Lock down the Google Drive folder sharing (see README_SIMPLE.txt).
echo   3. Run RUN_LOGIN_SETUP.bat and log into county records.
echo   4. Run RUN_TEST_5_ROWS.bat to test on 5 rows.
echo   5. Run RUN_AI_REVIEW.bat for the full job.
echo ============================================================
pause
endlocal
