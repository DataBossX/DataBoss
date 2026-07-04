@echo off
REM ===================================================================
REM  Horizon Command Center -- double-click launcher (Windows)
REM
REM  Runs the full pipeline against your Horizon folder:
REM    scan -> unzip -> SHA256 dedup (to trash) -> snapshot backup ->
REM    auto-detect OGL+runsheet workbook -> chain out interest ->
REM    validate -> loop -> write versioned reports to
REM    <root>\rogermillsfinalreports  (log: <root>\horizon_audit.log)
REM
REM  Just double-click this file. To use a different folder, either edit
REM  HORIZON_ROOT below or drag-and-drop a folder onto this .bat.
REM ===================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- 1. Pick the Horizon root -------------------------------------
REM  Priority: folder dragged onto the .bat  >  HORIZON_ROOT env var  >  default
set "HORIZON_ROOT=D:\Desktop\Horizon"
if not "%~1"=="" set "HORIZON_ROOT=%~1"

echo(
echo ==================================================================
echo   HORIZON COMMAND CENTER
echo   Root: %HORIZON_ROOT%
echo ==================================================================
echo(

if not exist "%HORIZON_ROOT%" (
    echo [ERROR] Folder does not exist: %HORIZON_ROOT%
    echo         Edit HORIZON_ROOT in this .bat, or drag your Horizon
    echo         folder onto this file to run it against that folder.
    echo(
    pause
    exit /b 1
)

REM --- 2. Find a Python launcher ------------------------------------
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

REM --- 3. Install dependencies (first run only; safe to repeat) -----
echo Installing/verifying dependencies...
%PY% -m pip install --quiet --disable-pip-version-check -r "%~dp0horizon\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Dependency install failed. See the messages above.
    echo(
    pause
    exit /b 1
)

REM --- 4. Run the Command Center -----------------------------------
echo(
echo Running Horizon...
echo(
%PY% "%~dp0horizon\main.py" --root "%HORIZON_ROOT%"
set "RC=%ERRORLEVEL%"

echo(
echo ==================================================================
if "%RC%"=="0" (
    echo   DONE. Final reports are in:
    echo     %HORIZON_ROOT%\rogermillsfinalreports
    echo   Audit log:
    echo     %HORIZON_ROOT%\horizon_audit.log
) else (
    echo   Finished with issues (exit code %RC%). Check the audit log:
    echo     %HORIZON_ROOT%\horizon_audit.log
)
echo ==================================================================
echo(
pause
endlocal
