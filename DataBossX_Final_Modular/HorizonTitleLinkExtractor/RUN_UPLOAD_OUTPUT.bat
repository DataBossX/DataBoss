@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - UPLOAD OUTPUT
REM Uploads the latest output workbook + logs to the Google Drive folder
REM (into a timestamped _AI_Updated_Reports subfolder). If Drive is not
REM configured, prints exact manual-upload instructions.
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Not installed yet. Run INSTALL.bat first.
    pause
    exit /b 1
)
if not exist ".env" (
    echo ERROR: .env not found. Copy .env.example to .env first.
    pause
    exit /b 1
)

echo ============================================================
echo  UPLOADING LATEST OUTPUT TO GOOGLE DRIVE
echo ============================================================

".venv\Scripts\python.exe" title_link_extractor.py --upload-only

echo.
pause
endlocal
