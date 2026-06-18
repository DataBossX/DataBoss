@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - RUN TESTS
REM Runs the automated logic test suite (no network / no API keys required).
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv not found. Please run INSTALL.bat first.
    pause
    exit /b 1
)

call "venv\Scripts\python.exe" -m pytest

echo.
pause
endlocal
