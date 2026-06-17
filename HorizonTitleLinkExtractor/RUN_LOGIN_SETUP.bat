@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - LOGIN SETUP
REM Opens a Playwright Chromium browser so you can log into the county-record
REM website manually. After you log in and close the browser, your session is
REM saved to .auth\county_state.json so the automation can reuse it.
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
echo   COUNTY RECORDS LOGIN SETUP
echo ============================================================
echo.
echo A browser window will open in a moment.
echo   1. Navigate to the county records website if needed.
echo   2. Log in completely (enter username/password, solve any captcha).
echo   3. Make sure you can see records / search results.
echo   4. Return to this window and press ENTER to save your session.
echo.
echo SECURITY: the saved file .auth\county_state.json contains your login
echo cookies. Do NOT upload, email, commit, or share it. Keep it local.
echo.

call "venv\Scripts\python.exe" title_link_extractor.py --login-setup

echo.
echo Login setup finished. Your session (if saved) is in .auth\county_state.json
echo.
pause
endlocal
