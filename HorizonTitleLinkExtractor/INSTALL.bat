@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - INSTALL
REM Creates a local Python virtual environment, installs dependencies,
REM installs the Playwright Chromium browser, and creates working folders.
REM ============================================================================
setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   HorizonTitleLinkExtractor - INSTALL
echo ============================================================
echo.

REM --- 1. Find Python -------------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found on your PATH.
    echo Please install Python 3.11 or newer from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [1/5] Creating local Python virtual environment (venv)...
if not exist "venv\Scripts\python.exe" (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
) else (
    echo       venv already exists - reusing it.
)

echo.
echo [2/5] Installing Python packages from requirements.txt...
call "venv\Scripts\python.exe" -m pip install --upgrade pip
call "venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed. Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo [3/5] Installing the Playwright Chromium browser...
call "venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 (
    echo [WARN] Playwright browser install reported a problem. You may need to rerun INSTALL.bat.
)

echo.
echo [4/5] Creating working folders...
if not exist "input"  mkdir "input"
if not exist "output" mkdir "output"
if not exist "logs"   mkdir "logs"
if not exist "temp"   mkdir "temp"
if not exist "debug"  mkdir "debug"
if not exist ".auth"  mkdir ".auth"

echo.
echo [5/5] Checking for your .env file...
if not exist ".env" (
    echo       No .env file found. Copying .env.example to .env ...
    copy ".env.example" ".env" >nul
    echo       --> IMPORTANT: open .env in Notepad and paste your API keys.
) else (
    echo       .env already exists - good.
)

echo.
echo ============================================================
echo   INSTALL COMPLETE
echo ============================================================
echo.
echo NEXT STEPS:
echo   1. Open the file ".env" in Notepad and paste your OPENAI_API_KEY.
echo   2. Lock down your Google Drive folder permissions (see README_SIMPLE.txt).
echo   3. Run  RUN_LOGIN_SETUP.bat  and log into the county records website.
echo   4. Run  RUN_TEST_5_ROWS.bat  to test on 5 rows.
echo   5. Run  RUN_AI_REVIEW.bat    to process the full workbook.
echo.
pause
endlocal
