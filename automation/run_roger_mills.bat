@echo off
REM ============================================================
REM  Roger Mills Cursory Title Report Builder (codexv2)
REM  Double-click this file, answer the prompts, done.
REM ============================================================
setlocal enabledelayedexpansion
title Roger Mills Title Report Builder (codexv2)

echo ============================================================
echo   Roger Mills Cursory Title Report Builder (codexv2)
echo ============================================================
echo.

REM --- locate a Python launcher ---
set PYEXE=py
where py >nul 2>nul || set PYEXE=python
where %PYEXE% >nul 2>nul || (
  echo ERROR: Python was not found. Install Python 3 from https://python.org
  echo        then run this file again.
  pause & exit /b 1
)

echo Installing/updating the required Python packages (first run only)...
%PYEXE% -m pip install --upgrade openpyxl pandas pdfplumber PyMuPDF pytesseract Pillow python-dateutil rapidfuzz python-docx
echo.

echo Verifying the install with a quick self-test...
%PYEXE% "%~dp0roger_mills_title_report_builder.py" --self-test
if errorlevel 1 (
  echo.
  echo Self-test FAILED. Fix the errors above before running on real data.
  pause & exit /b 1
)
echo.

set /p ROOT=Enter the folder with your Roger Mills files (e.g. D:\Desktop\Horizon\Roger Mills):
if "%ROOT%"=="" ( echo No folder entered. & pause & exit /b 1 )

set "SECTION=31-12N-24W"
set /p SECTION=Enter the section label [31-12N-24W]:

set "ACRES="
set /p ACRES=Enter gross mineral acres for NMA chaining [leave blank to skip]:

set "PREVIEW="
set /p PREVIEW=Preview only, change nothing? (y/N):

set "ACREOPT="
if not "%ACRES%"=="" set "ACREOPT=--gross-acres %ACRES%"
set "DRYOPT="
if /i "%PREVIEW%"=="y" set "DRYOPT=--dry-run"

echo.
echo Running builder on "%ROOT%" (section %SECTION%) ...
echo ------------------------------------------------------------
%PYEXE% "%~dp0roger_mills_title_report_builder.py" --root "%ROOT%" --section "%SECTION%" %ACREOPT% %DRYOPT%
echo ------------------------------------------------------------
echo.
echo Done. Open the "rogermillsfinalreports" folder inside:
echo   %ROOT%
echo Start with final_validation_summary_codexv2.txt (PERFECTION CHECKLIST)
echo and the *_interest_chain_report_codexv2.html preview.
echo.
pause
endlocal
