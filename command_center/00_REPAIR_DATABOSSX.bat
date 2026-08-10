@echo off
setlocal enabledelayedexpansion
title DataBossX Command Center - Repair
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
echo   DataBossX Command Center - Safe Repair
echo ============================================
echo This only touches files DataBossX itself created
echo (the runtime dir's lock/identity/port files if stale). It
echo never touches Penterra/Horizon client sources, evidence, or
echo any process it cannot positively verify as its own.
echo.

if not exist "!RUNTIME_DIR!" (
    mkdir "!RUNTIME_DIR!"
    echo Created missing runtime dir: !RUNTIME_DIR!
) else (
    echo Runtime dir present: !RUNTIME_DIR!
)

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

rem Same shared identity_cli.py validator as START/STOP/DIAGNOSTICS.
rem Distinguishes: a verified running instance (left alone -- stop it
rem first); a truly stale receipt (PID dead -- cleared); and a live but
rem mismatched/unowned process (refused -- receipt cleared only if it was
rem STALE/MALFORMED, the process itself is never touched).
!PY_CMD! "%~dp0identity_cli.py" --runtime-dir "!RUNTIME_DIR!" repair > "!RUNTIME_DIR!\_repair_result.json" 2>nul
set "REPAIR_RC=!ERRORLEVEL!"
type "!RUNTIME_DIR!\_repair_result.json" 2>nul
del "!RUNTIME_DIR!\_repair_result.json" >nul 2>nul

if exist "!RUNTIME_DIR!\databossx.db" (
    echo Found existing database - leaving it in place ^(migrations run automatically on next start^).
) else (
    echo No database yet - one will be created cleanly on next start.
)

echo.
if "!REPAIR_RC!"=="1" (
    echo [SAFETY REFUSAL] See message above -- a live, unowned process was left untouched.
) else (
    echo Repair complete. Run 00_START_DATABOSSX.bat next.
)
if "%NONINTERACTIVE%"=="0" pause
