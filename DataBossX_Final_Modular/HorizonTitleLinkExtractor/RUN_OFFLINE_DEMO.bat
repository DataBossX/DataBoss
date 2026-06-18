@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - OFFLINE DEMO
REM Runs the ENTIRE pipeline with synthetic documents and a mock AI - no API
REM keys, no county login, no internet needed. Great for a first look at what
REM the output workbook and review report will look like.
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Not installed yet. Run INSTALL.bat first.
    pause
    exit /b 1
)

echo ============================================================
echo  OFFLINE DEMO (no keys, no browser, no network)
echo ============================================================

".venv\Scripts\python.exe" title_link_extractor.py --offline-demo

echo.
echo ============================================================
echo  DEMO FINISHED
echo  - Open the review workbook in output\ (ends in _AI_REVIEW_*.xlsx)
echo  - Open the matching *_REPORT.html in your browser
echo  - See logs\run_log.csv, logs\summary.csv, logs\run_manifest.json
echo ============================================================
pause
endlocal
