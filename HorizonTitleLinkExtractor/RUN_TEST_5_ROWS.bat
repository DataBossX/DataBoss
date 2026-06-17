@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - TEST 5 ROWS
REM Processes only the first 5 rows that have a document link, so you can
REM verify everything works before running the full job.
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found. Please run INSTALL.bat first.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   TEST RUN - 5 LINKED ROWS
echo ============================================================
echo.

call "venv\Scripts\python.exe" title_link_extractor.py --test

echo.
echo ============================================================
echo   TEST RUN FINISHED
echo ============================================================
echo Open the output workbook listed above and review the AI columns.
echo.
pause
endlocal
