@echo off
REM ── One-click build of the Roger Mills 31-12N-24W report ────────────────────
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call INSTALL_OR_REPAIR.bat
call ".venv\Scripts\activate.bat"

set SRC=%1
set OUT=%2
set EVID=%3
if "%SRC%"=="" set SRC=input.xlsx
if "%OUT%"=="" set OUT=31-12N-24W_Roger_Mills_Cursory_Title_Report.xlsx

echo Building report from "%SRC%" -> "%OUT%" ...
python -m title_report_builder.report.build_roger_mills "%SRC%" "%OUT%" %EVID%
echo Done.
pause
endlocal
