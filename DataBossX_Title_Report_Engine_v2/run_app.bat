@echo off
REM ==========================================================================
REM  DataBossX Title Report Engine v2 -- Windows launcher
REM  Run this on the machine where the real Horizon files live (your D: drive).
REM ==========================================================================

setlocal
cd /d "%~dp0"

REM --- pick a Python launcher ------------------------------------------------
where py >nul 2>nul && (set PYEXE=py) || (set PYEXE=python)

echo Installing/updating dependencies...
%PYEXE% -m pip install --quiet --upgrade -r requirements.txt

REM --- configure your job here ----------------------------------------------
set ROOT=D:\Desktop\Horizon
set SECTION=31-12N-24W
set OUTPUT=D:\Desktop\Horizon\SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx

echo.
echo Running Title Report Engine v2 on "%ROOT%" ...
%PYEXE% app.py --root "%ROOT%" --section "%SECTION%" --output "%OUTPUT%"

echo.
echo Done. Final report: %OUTPUT%
echo Audit log:      %~dp0logs\SECTION31_AUDIT_LOG.xlsx
echo Source ranking: %~dp0logs\SOURCE_FILE_RANKING.xlsx
endlocal
pause
