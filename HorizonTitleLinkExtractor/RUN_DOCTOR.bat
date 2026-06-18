@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - DOCTOR (preflight checks)
REM Verifies Python, packages, config, API keys, county login, and folders.
REM Run this any time something is not working.
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found. Please run INSTALL.bat first.
    pause
    exit /b 1
)

call "venv\Scripts\python.exe" title_link_extractor.py --doctor

echo.
pause
endlocal
