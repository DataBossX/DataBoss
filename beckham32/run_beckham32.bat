@echo off
REM ============================================================
REM  BECKHAM 32 REPORT BUILDER - one-click launcher
REM  Merges the NHE + original Section 32-11N-25W cursory
REM  reports into one best-evidence workbook with a complete
REM  runsheet and per-tract chain-outs. Sources are read-only.
REM
REM  Put this folder on the machine that has the report files,
REM  then double-click. Or drag the folder containing the
REM  reports onto this .bat.
REM ============================================================
setlocal
cd /d "%~dp0"

set "PYCMD="
where py >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD where python >nul 2>nul && set "PYCMD=python"
if not defined PYCMD (
    echo ERROR: Python is not installed. Get it from python.org and tick
    echo "Add python.exe to PATH" during install.
    pause & exit /b 1
)

%PYCMD% -m pip install --disable-pip-version-check -q openpyxl
if errorlevel 1 (
    echo ERROR: could not install openpyxl. Are you online?
    pause & exit /b 1
)

if "%~1"=="" (
    %PYCMD% "%~dp0beckham32_report_builder.py"
) else (
    %PYCMD% "%~dp0beckham32_report_builder.py" --search "%~1"
)
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
    echo DONE. Look for 32-11N-25W_..._MERGED_BEST_^<timestamp^>.xlsx
    echo next to the NHE report. Sources were not modified.
) else (
    echo THE RUN DID NOT COMPLETE. Scroll up for the ERROR lines.
)
pause
exit /b %RC%
