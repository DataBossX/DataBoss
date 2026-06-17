@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - FULL AI REVIEW
REM Runs the full configured job over the whole workbook.
REM Will refuse to start if .env or county login state is missing.
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found. Please run INSTALL.bat first.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] No .env file found. Run INSTALL.bat and add your API keys.
    pause
    exit /b 1
)

if not exist ".auth\county_state.json" (
    echo [ERROR] No county login session found (.auth\county_state.json).
    echo Please run RUN_LOGIN_SETUP.bat and log into the county site first.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   FULL AI REVIEW
echo ============================================================
echo.

call "venv\Scripts\python.exe" title_link_extractor.py --full

echo.
echo ============================================================
echo   FULL AI REVIEW FINISHED
echo ============================================================
echo Check the output\ folder (and your Drive AI output folder) for results.
echo.
pause
endlocal
