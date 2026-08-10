@echo off
setlocal enabledelayedexpansion
title DataBossX Command Center - Stop
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

echo Stopping DataBossX Command Center...

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
if "!PY_CMD!"=="" (
    echo [ERROR] No working Python interpreter found on PATH.
    if "%NONINTERACTIVE%"=="0" pause
    exit /b 1
)

rem Identity comes ONLY from the shared identity_cli.py validator -- the
rem same one START/REPAIR/DIAGNOSTICS and the server's own single-instance
rem lock use. It only ever terminates a PID whose creation time,
rem executable, server path, and runtime dir all match our own receipt --
rem never a bare PID or "looks like python.exe" match.
!PY_CMD! "%~dp0identity_cli.py" --runtime-dir "!RUNTIME_DIR!" stop > "!RUNTIME_DIR!\_stop_result.json" 2>nul
set "STOP_RC=!ERRORLEVEL!"
type "!RUNTIME_DIR!\_stop_result.json" 2>nul
del "!RUNTIME_DIR!\_stop_result.json" >nul 2>nul

if "!STOP_RC!"=="1" (
    echo.
    echo [SAFETY REFUSAL] See message above -- no process was touched.
    if "%NONINTERACTIVE%"=="0" pause
    exit /b 1
)

echo.
echo Done.
if "%NONINTERACTIVE%"=="0" pause
