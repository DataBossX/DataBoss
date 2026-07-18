@echo off
REM ======================================================================
REM  DataBossX Command Center -- one-click launcher (Windows)
REM
REM  Just double-click this file. On the first run it sets up a private,
REM  isolated Python environment (the .dbxvenv folder), installs what it
REM  needs, self-checks, then shows a simple menu:
REM
REM     1) Run the built-in demo       (proves everything works, no data)
REM     2) Run one of your projects    (Horizon, Penterra, Ryder, ...)
REM     3) Quick interest calculator   (mineral / WI / NRI)
REM     4) Self-check (doctor)
REM     5) Open the last output folder
REM     6) Quit
REM
REM  To reset everything, delete the .dbxvenv folder and run this again.
REM  Nothing here ever changes your source files.
REM ======================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"
title DataBossX Command Center

REM --- 1. Find a Python launcher ---------------------------------------
set "PY=py"
where py >nul 2>nul || set "PY=python"
%PY% --version >nul 2>nul
if errorlevel 1 (
    echo(
    echo [PROBLEM] Python was not found on this computer.
    echo           Install Python 3.10 or newer from:
    echo             https://www.python.org/downloads/
    echo           During install, TICK the box "Add Python to PATH".
    echo(
    pause
    exit /b 1
)

REM --- 2. Create a private environment (first run only) ----------------
set "VPY=.dbxvenv\Scripts\python.exe"
if not exist "%VPY%" (
    echo Setting up DataBossX for the first time. This can take a minute...
    %PY% -m venv .dbxvenv
    if errorlevel 1 (
        echo [PROBLEM] Could not create the private environment.
        pause
        exit /b 1
    )
)

REM --- 3. Install / verify dependencies (safe to repeat) --------------
echo Checking components...
"%VPY%" -m pip install --quiet --disable-pip-version-check ^
    pydantic openpyxl reportlab python-docx
if errorlevel 1 (
    echo [PROBLEM] Could not install components. Check your internet connection.
    pause
    exit /b 1
)

REM --- 4. Self-check ---------------------------------------------------
echo(
"%VPY%" -m databossx doctor
echo(

:menu
echo ======================================================================
echo   DataBossX Command Center
echo ======================================================================
echo   1) Run the built-in demo (no client data needed)
echo   2) Run one of your projects
echo   3) Quick interest calculator (mineral / WI / NRI)
echo   4) Self-check (doctor)
echo   5) Open the last output folder
echo   6) Quit
echo ----------------------------------------------------------------------
set "choice="
set /p "choice=Type a number and press Enter: "

if "%choice%"=="1" goto do_demo
if "%choice%"=="2" goto do_project
if "%choice%"=="3" goto do_calc
if "%choice%"=="4" goto do_doctor
if "%choice%"=="5" goto do_open
if "%choice%"=="6" goto end
echo Please type a number from 1 to 6.
echo(
goto menu

:do_demo
echo(
"%VPY%" -m databossx demo
set "LAST=examples\projects\GOLDEN-DEMO\databossx_output"
echo(
pause
goto menu

:do_project
echo(
echo Registered projects:
"%VPY%" -m databossx list
set "proj="
set /p "proj=Project key (e.g. horizon), or blank to cancel: "
if "%proj%"=="" goto menu
set "folder="
set /p "folder=Folder with the files (blank = use the default): "
echo(
if "%folder%"=="" (
    "%VPY%" -m databossx run --project "%proj%"
) else (
    "%VPY%" -m databossx run --project "%proj%" --root "%folder%"
    set "LAST=%folder%\databossx_output"
)
echo(
pause
goto menu

:do_calc
echo(
echo Examples:  mineral=1/2 gross=160   or   wi=1 royalty=1/8
set "mi="
set "gr="
set "wi="
set "ry="
set /p "mi=Mineral interest (blank to skip): "
set /p "gr=Gross acres (blank to skip): "
set /p "wi=Working interest (blank to skip): "
set /p "ry=Royalty rate (blank to skip): "
set "ARGS="
if not "%mi%"=="" set "ARGS=!ARGS! --mineral %mi%"
if not "%gr%"=="" set "ARGS=!ARGS! --gross %gr%"
if not "%wi%"=="" set "ARGS=!ARGS! --wi %wi%"
if not "%ry%"=="" set "ARGS=!ARGS! --royalty %ry%"
echo(
"%VPY%" -m databossx calc !ARGS!
echo(
pause
goto menu

:do_doctor
echo(
"%VPY%" -m databossx doctor
echo(
pause
goto menu

:do_open
if defined LAST (
    if exist "%LAST%" ( start "" "%LAST%" ) else ( echo No output folder yet -- run a project first. )
) else (
    echo No output folder yet -- run the demo or a project first.
)
echo(
goto menu

:end
echo(
echo Goodbye.
endlocal
