@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - UPLOAD OUTPUT
REM Uploads the latest output workbook + logs + summary to the Google Drive
REM folder (timestamped AI output subfolder). Skips files already uploaded.
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
echo   UPLOAD LATEST OUTPUT TO GOOGLE DRIVE
echo ============================================================
echo.

call "venv\Scripts\python.exe" title_link_extractor.py --upload-only

echo.
pause
endlocal
