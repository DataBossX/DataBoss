@echo off
REM ============================================================
REM  SECTION 31 QA AUDITOR - one-click launcher
REM  Double-click this file. It will:
REM    1. find Python (installs nothing else on your system)
REM    2. install the one required package (openpyxl)
REM    3. run the read-only QA audit on the Horizon folders
REM  Originals are NEVER modified. All output goes to a new
REM  Section31_QA_Output_<timestamp> folder under D:\Desktop\Horizon.
REM
REM  Optional: drag a folder onto this .bat to scan that folder
REM  instead of the default Horizon folders.
REM ============================================================
setlocal
cd /d "%~dp0"

REM ---- find Python (py launcher first, then python) ----
set "PYCMD="
where py >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD where python >nul 2>nul && set "PYCMD=python"
if not defined PYCMD (
    echo.
    echo ERROR: Python is not installed or not on PATH.
    echo Install it from https://www.python.org/downloads/
    echo IMPORTANT: tick "Add python.exe to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo Installing/checking the required package (openpyxl)...
%PYCMD% -m pip install --disable-pip-version-check -q -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo ERROR: could not install openpyxl. Are you online?
    echo Try manually:  %PYCMD% -m pip install openpyxl
    echo.
    pause
    exit /b 1
)

echo.
if "%~1"=="" (
    echo Running the Section 31 QA audit on the default Horizon folders...
    %PYCMD% "%~dp0section31_qa.py"
) else (
    echo Running the Section 31 QA audit on: %~1
    %PYCMD% "%~dp0section31_qa.py" --roots "%~1"
)
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
    echo DONE. Open the newest Section31_QA_Output_... folder and read
    echo SECTION31_QA_SUMMARY.txt first, then qa_defects.xlsx.
) else (
    echo THE RUN DID NOT COMPLETE (exit code %RC%^). Scroll up for the ERROR
    echo lines, or open run_log.txt in the output folder if one was created.
    echo No original file was modified.
)
echo.
pause
exit /b %RC%
