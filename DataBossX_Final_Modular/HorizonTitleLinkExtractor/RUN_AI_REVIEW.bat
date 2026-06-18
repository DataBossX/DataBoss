@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - FULL AI REVIEW
REM Runs the full configured job. REVIEW ONLY by default (no original cells
REM are overwritten unless apply_corrections=true in config.yaml).
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Not installed yet. Run INSTALL.bat first.
    pause
    exit /b 1
)

REM --- Must have .env ---------------------------------------------------------
if not exist ".env" (
    echo ERROR: .env not found.
    echo Copy .env.example to .env and add your OPENAI_API_KEY first.
    pause
    exit /b 1
)

REM --- Must have county auth state -------------------------------------------
if not exist ".auth\county_state.json" (
    echo ERROR: County login state not found (.auth\county_state.json).
    echo Run RUN_LOGIN_SETUP.bat first and log into the county-records site.
    pause
    exit /b 1
)

REM --- Warn if no Drive upload configured ------------------------------------
set "DRIVE_OK="
findstr /R /C:"GOOGLE_DRIVE_LOCAL_SYNC_PATH=..*" ".env" >nul 2>nul && set "DRIVE_OK=1"
findstr /R /C:"GOOGLE_OAUTH_CLIENT_SECRET_JSON=..*" ".env" >nul 2>nul && set "DRIVE_OK=1"
findstr /R /C:"GOOGLE_APPLICATION_CREDENTIALS=..*" ".env" >nul 2>nul && set "DRIVE_OK=1"
if not defined DRIVE_OK (
    echo.
    echo WARNING: No Google Drive upload is configured in .env.
    echo The output will be saved locally in output\ and manual upload
    echo instructions will be printed at the end.
    echo.
)

echo ============================================================
echo  RUNNING FULL AI REVIEW
echo ============================================================

".venv\Scripts\python.exe" title_link_extractor.py --run

echo.
echo ============================================================
echo  FULL REVIEW FINISHED
echo  - Output workbook: output\*_AI_REVIEW_*.xlsx
echo  - Logs: logs\run_log.csv, logs\summary.csv, logs\errors.log
echo ============================================================
pause
endlocal
