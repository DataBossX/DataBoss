@echo off
setlocal enabledelayedexpansion
title DataBossX Command Center - Diagnostics
cd /d "%~dp0"

set "SANDBOX_MODE=0"
set "SANDBOX_ROOT="
:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--sandbox" (
    set "SANDBOX_MODE=1"
    shift
    goto parse_args
)
if /I "%~1"=="--sandbox-root" (
    set "SANDBOX_MODE=1"
    set "SANDBOX_ROOT=%~2"
    shift
    shift
    goto parse_args
)
shift
goto parse_args
:args_done

set "NONINTERACTIVE=0"
if /I "%DATABOSSX_NONINTERACTIVE%"=="1" set "NONINTERACTIVE=1"

if "%SANDBOX_MODE%"=="1" (
    if "%SANDBOX_ROOT%"=="" set "SANDBOX_ROOT=%LOCALAPPDATA%\DataBossX\FirstRunSandbox"
    set "RUNTIME_DIR=!SANDBOX_ROOT!\runtime"
) else (
    set "RUNTIME_DIR=%~dp0runtime"
)

echo ============================================
echo   DataBossX Command Center - Diagnostics
echo ============================================
echo.
echo -- Python --
where python 2>nul
where py 2>nul
python --version 2>nul

set "PY_CMD="
where py >nul 2>nul
if !ERRORLEVEL!==0 (
    py -3 --version >nul 2>nul
    if !ERRORLEVEL!==0 set "PY_CMD=py -3"
)
if "!PY_CMD!"=="" (
    where python >nul 2>nul
    if !ERRORLEVEL!==0 (
        python --version >nul 2>nul
        if !ERRORLEVEL!==0 set "PY_CMD=python"
    )
)

echo.
echo -- Files --
if exist server.py (echo server.py: OK) else (echo server.py: MISSING)
if exist static\index.html (echo static\index.html: OK) else (echo static\index.html: MISSING)
if exist "!RUNTIME_DIR!\databossx.db" (echo databossx.db: OK) else (echo databossx.db: not yet created - normal on first run)

echo.
echo -- Effective roots and runtime paths ^(from the same identity validator
echo    START/STOP/REPAIR use -- not hard-coded defaults^) --
if "!PY_CMD!"=="" (
    echo [ERROR] No working Python interpreter found on PATH -- cannot query identity.
) else (
    !PY_CMD! "%~dp0identity_cli.py" --runtime-dir "!RUNTIME_DIR!" diagnostics
)

echo.
echo -- Server health check --
if exist "!RUNTIME_DIR!\port.txt" (
    for /f "usebackq" %%q in ("!RUNTIME_DIR!\port.txt") do set "PORT=%%q"
    echo Reported port: !PORT!
    curl -s "http://127.0.0.1:!PORT!/api/health" 2>nul
    echo.
    if errorlevel 1 echo Could not reach http://127.0.0.1:!PORT! -- check "!RUNTIME_DIR!\server.log".
) else (
    echo Skipped - no known port yet.
)

echo.
echo -- Last 20 lines of server.log --
if exist "!RUNTIME_DIR!\server.log" (
    powershell -command "Get-Content '!RUNTIME_DIR!\server.log' -Tail 20"
) else (
    echo No server.log yet.
)
echo.
if "%NONINTERACTIVE%"=="0" pause
