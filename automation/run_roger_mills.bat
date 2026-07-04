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

echo You can point at up to three folders (leave 2 and 3 blank if you have one).
set /p ROOT1=Folder 1 (e.g. D:\Desktop\Horizon\Roger Mills):
if "%ROOT1%"=="" ( echo No folder entered. & pause & exit /b 1 )
set /p ROOT2=Folder 2 (optional, e.g. D:\Desktop\Horizon\Roger Mills 2):
set /p ROOT3=Folder 3 (optional, e.g. D:\Desktop\Horizon\Roger Mills 3):

set "ROOTS=--root "%ROOT1%""
if not "%ROOT2%"=="" set "ROOTS=%ROOTS% "%ROOT2%""
if not "%ROOT3%"=="" set "ROOTS=%ROOTS% "%ROOT3%""

set "SECTION=31-12N-24W"
set /p SECTION=Section / tract label [31-12N-24W]:

set "ACRES="
set /p ACRES=Gross mineral acres for NMA chaining [leave blank to skip]:

set "FINALCOPY="
set /p FINALCOPY=Path to your existing "final copy" to fix [leave blank to skip]:

set "PREVIEW="
set /p PREVIEW=Preview only, change nothing? (y/N):

set "ACREOPT="
if not "%ACRES%"=="" set "ACREOPT=--gross-acres %ACRES%"
set "FCOPT="
if not "%FINALCOPY%"=="" set "FCOPT=--final-copy "%FINALCOPY%""
set "DRYOPT="
if /i "%PREVIEW%"=="y" set "DRYOPT=--dry-run"

echo.
echo Running builder (section %SECTION%) ...
echo ------------------------------------------------------------
%PYEXE% "%~dp0roger_mills_title_report_builder.py" %ROOTS% --section "%SECTION%" --tract "%SECTION%" %ACREOPT% %FCOPT% %DRYOPT%
echo ------------------------------------------------------------
echo.
echo Done. Open the "rogermillsfinalreports" folder in the parent of your folders.
echo Start with final_validation_summary_codexv2.txt (PERFECTION CHECKLIST)
echo and the *_interest_chain_report_codexv2.html preview.
echo.
pause
endlocal
