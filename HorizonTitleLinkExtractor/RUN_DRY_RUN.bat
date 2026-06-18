@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - DRY RUN
REM Opens each document link and confirms the document is visible, but does
REM NOT call any AI model (no cost). Use this to verify the workbook, the
REM hyperlinks, your county login, and the "View" clicking all work before
REM you spend money on a full AI review.
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found. Please run INSTALL.bat first.
    pause
    exit /b 1
)

if not exist ".auth\county_state.json" (
    echo [ERROR] No county login session found (.auth\county_state.json).
    echo Please run RUN_LOGIN_SETUP.bat first.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   DRY RUN - capture documents, NO AI calls
echo ============================================================
echo.

call "venv\Scripts\python.exe" title_link_extractor.py --dry-run

echo.
echo Open logs\report.html to see which links opened successfully.
echo.
pause
endlocal
