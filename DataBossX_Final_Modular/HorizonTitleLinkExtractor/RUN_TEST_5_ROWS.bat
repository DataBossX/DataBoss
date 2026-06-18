@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - TEST (5 rows)
REM Processes only the first few linked rows (test_mode_rows in config.yaml).
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Not installed yet. Run INSTALL.bat first.
    pause
    exit /b 1
)
if not exist ".env" (
    echo ERROR: .env not found. Copy .env.example to .env and add your API keys.
    pause
    exit /b 1
)

echo ============================================================
echo  RUNNING TEST (first few linked rows)
echo ============================================================

".venv\Scripts\python.exe" title_link_extractor.py --test

echo.
echo ============================================================
echo  TEST FINISHED
echo  - Output workbook is in the output\ folder (name ends in _AI_REVIEW_*.xlsx)
echo  - Open it and check the AI review columns on the right.
echo  - Logs are in logs\run_log.csv and logs\summary.csv
echo ============================================================
pause
endlocal
