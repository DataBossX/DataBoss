@echo off
REM ===================================================================
REM  Roger Mills Title Report Builder -- Sections 12 & 14 launcher
REM
REM  Runs roger_mills_title_report_builder.py once for Section 12 and
REM  once for Section 14, back-to-back, so both come out formatted the
REM  same way as the already-finished Section 11 / 13 / 15 reports:
REM    - counts and documents every image (image_inventory_codexv1.csv
REM      + an "Image Index" sheet appended to the report workbook)
REM    - writes the full support-file documentation trail
REM    - packages a dated, ready-to-turn-in delivery zip for each section
REM
REM  EDIT THE FOUR PATHS BELOW to match where your Section 12 and
REM  Section 14 source folders actually live on this machine, then just
REM  double-click this file. Nothing is deleted or overwritten; originals
REM  are backed up before anything is read.
REM ===================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- 1. Section source folders (EDIT THESE) ------------------------
if not defined SECTION12_ROOT set "SECTION12_ROOT=D:\DataBoss\DataBossX_Final_Modular\Section 12"
if not defined SECTION14_ROOT set "SECTION14_ROOT=D:\DataBoss\DataBossX_Final_Modular\Section 14"

echo(
echo ==================================================================
echo   ROGER MILLS TITLE REPORT BUILDER -- Sections 12 and 14
echo   Section 12 root: %SECTION12_ROOT%
echo   Section 14 root: %SECTION14_ROOT%
echo ==================================================================
echo(

REM --- 2. Find a Python launcher --------------------------------------
set "PY=py"
where py >nul 2>nul || set "PY=python"
%PY% --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    echo         and check "Add Python to PATH" during install.
    echo(
    pause
    exit /b 1
)

REM --- 3. Install dependencies (first run only; safe to repeat) ------
echo Installing/verifying dependencies...
%PY% -m pip install --quiet --disable-pip-version-check ^
    openpyxl pandas pdfplumber PyMuPDF pytesseract Pillow python-dateutil rapidfuzz
if errorlevel 1 (
    echo [ERROR] Dependency install failed. See the messages above.
    echo(
    pause
    exit /b 1
)

set "RC_TOTAL=0"

REM --- 4. Section 12 ---------------------------------------------------
if exist "%SECTION12_ROOT%" (
    echo(
    echo ------------------------------------------------------------------
    echo   Building Section 12...
    echo ------------------------------------------------------------------
    %PY% "%~dp0roger_mills_title_report_builder.py" ^
        --root "%SECTION12_ROOT%" ^
        --output "%SECTION12_ROOT%\Section_12_Roger_Mills_Cursory_Title_Report_codexv1.xlsx" ^
        --support-dir "%SECTION12_ROOT%\files" ^
        --section "Section 12"
    if errorlevel 1 set "RC_TOTAL=1"
) else (
    echo [ERROR] Section 12 folder does not exist: %SECTION12_ROOT%
    echo         Edit SECTION12_ROOT at the top of this .bat.
    set "RC_TOTAL=1"
)

REM --- 5. Section 14 ---------------------------------------------------
if exist "%SECTION14_ROOT%" (
    echo(
    echo ------------------------------------------------------------------
    echo   Building Section 14...
    echo ------------------------------------------------------------------
    %PY% "%~dp0roger_mills_title_report_builder.py" ^
        --root "%SECTION14_ROOT%" ^
        --output "%SECTION14_ROOT%\Section_14_Roger_Mills_Cursory_Title_Report_codexv1.xlsx" ^
        --support-dir "%SECTION14_ROOT%\files" ^
        --section "Section 14"
    if errorlevel 1 set "RC_TOTAL=1"
) else (
    echo [ERROR] Section 14 folder does not exist: %SECTION14_ROOT%
    echo         Edit SECTION14_ROOT at the top of this .bat.
    set "RC_TOTAL=1"
)

echo(
echo ==================================================================
if "%RC_TOTAL%"=="0" (
    echo   DONE. For each section, check the console output above for:
    echo     - TOTAL IMAGES found
    echo     - Delivery package: ...Title_Report_Delivery_Package_(MM-DD-YYYY).zip
    echo   Each zip is sitting next to that section's output workbook,
    echo   ready to turn in.
) else (
    echo   Finished with issues on at least one section. Scroll up to see
    echo   which section failed and why.
)
echo ==================================================================
echo(
pause
endlocal
