@echo off
REM ===================================================================
REM  SECTION 31-12N-24W ROGER MILLS -- Report Machine launcher (Windows)
REM
REM  Double-click to:
REM    * auto-detect Python (py launcher or python on PATH)
REM    * create a private virtual environment (.venv), once
REM    * auto-install dependencies, once
REM    * create D:\Desktop\Horizon\Roger Mills + subfolders
REM    * load your .env securely (never printing secrets)
REM    * open the Streamlit dashboard in your browser
REM
REM  Put this .bat in the same folder as the "section31_app" folder.
REM  It will also drop a copy of itself on your Desktop on first run.
REM ===================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

set "APP_HOME=%~dp0"
if "%APP_HOME:~-1%"=="\" set "APP_HOME=%APP_HOME:~0,-1%"

REM --- Locate the app package --------------------------------------
if not exist "%APP_HOME%\section31_app\app.py" (
    REM Maybe this .bat was launched from the Desktop copy; look for a
    REM sibling checkout via the SECTION31_APP_HOME env var.
    if defined SECTION31_APP_HOME set "APP_HOME=%SECTION31_APP_HOME%"
)
if not exist "%APP_HOME%\section31_app\app.py" (
    echo [ERROR] Could not find "section31_app\app.py" next to this launcher.
    echo         Keep Launch_Section31_Report_App.bat in the same folder as the
    echo         section31_app folder, or set SECTION31_APP_HOME to that folder.
    echo(
    pause
    exit /b 1
)

REM --- Choose the Roger Mills root ---------------------------------
if not defined SECTION31_ROOT set "SECTION31_ROOT=D:\Desktop\Horizon\Roger Mills"
if not "%~1"=="" set "SECTION31_ROOT=%~1"

echo(
echo ==================================================================
echo   SECTION 31-12N-24W ROGER MILLS -- REPORT MACHINE
echo   App:  %APP_HOME%\section31_app
echo   Data: %SECTION31_ROOT%
echo ==================================================================
echo(

REM --- Find a Python launcher --------------------------------------
set "PY=py"
where py >nul 2>nul || set "PY=python"
%PY% --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    echo         and check "Add Python to PATH" during install, then re-run.
    echo(
    pause
    exit /b 1
)

REM --- Create / reuse the virtual environment ----------------------
set "VENV=%APP_HOME%\.venv"
if not exist "%VENV%\Scripts\python.exe" (
    echo Creating virtual environment (first run only)...
    %PY% -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        echo(
        pause
        exit /b 1
    )
)
set "VPY=%VENV%\Scripts\python.exe"

REM --- Install / verify dependencies -------------------------------
echo Installing/verifying dependencies (first run is slow; later runs are fast)...
"%VPY%" -m pip install --quiet --disable-pip-version-check --upgrade pip
"%VPY%" -m pip install --quiet --disable-pip-version-check -r "%APP_HOME%\section31_app\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Dependency install failed. See the messages above.
    echo(
    pause
    exit /b 1
)

REM --- Create the folder structure + seed the template workbook ----
echo Preparing the Roger Mills folder...
"%VPY%" -c "import sys; sys.path.insert(0, r'%APP_HOME%'); from section31_app.config import Section31Config; from section31_app.env_utils import load_env; from section31_app.bootstrap import bootstrap; load_env(); bootstrap(Section31Config.from_env(r'%SECTION31_ROOT%'))"

REM --- Drop a copy of this launcher on the Desktop -----------------
set "DESKTOP=%USERPROFILE%\Desktop"
if exist "%DESKTOP%" (
    if not exist "%DESKTOP%\Launch_Section31_Report_App.bat" (
        copy /y "%~f0" "%DESKTOP%\Launch_Section31_Report_App.bat" >nul 2>nul
        REM Record where the app lives so the Desktop copy can find it.
        setx SECTION31_APP_HOME "%APP_HOME%" >nul 2>nul
        echo Placed a launcher shortcut on your Desktop.
    )
)

REM --- Launch the dashboard ----------------------------------------
echo(
echo Opening the dashboard in your browser...
echo (Leave this window open while you use the app. Close it to stop.)
echo(
set "SECTION31_ROOT=%SECTION31_ROOT%"
"%VPY%" -m streamlit run "%APP_HOME%\section31_app\app.py" --server.headless=false

echo(
echo Dashboard closed.
pause
endlocal
