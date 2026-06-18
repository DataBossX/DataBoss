@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - COUNTY LOGIN SETUP
REM Opens a Chromium browser. Log into the county-records site, then CLOSE the
REM browser window. Login cookies are saved to .auth\county_state.json (local).
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Not installed yet. Run INSTALL.bat first.
    pause
    exit /b 1
)

echo ============================================================
echo  COUNTY LOGIN SETUP
echo ============================================================
echo  A browser window will open.
echo   1. Go to your county-records website.
echo   2. Log in completely.
echo   3. When you can see records, CLOSE the browser window.
echo.
echo  Your login is saved locally to .auth\county_state.json
echo  Keep that file private. Never email, upload, commit, or share it.
echo ============================================================

".venv\Scripts\python.exe" title_link_extractor.py --login-setup

echo.
echo Done. You can now run RUN_TEST_5_ROWS.bat
pause
endlocal
