@echo off
REM ============================================================================
REM HorizonTitleLinkExtractor - DOCTOR (preflight check)
REM Verifies Python, dependencies, API keys, county login, Drive config, and
REM config.yaml BEFORE you run a real job. Fix any [FAIL] items it prints.
REM ============================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Not installed yet. Run INSTALL.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" title_link_extractor.py --doctor

echo.
pause
endlocal
