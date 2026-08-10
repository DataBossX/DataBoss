@echo off
setlocal enabledelayedexpansion
title DataBossX Command Center - Repair
cd /d "%~dp0"
echo ============================================
echo   DataBossX Command Center - Safe Repair
echo ============================================
echo This only touches files DataBossX itself created
echo (runtime\ folder, lock/port files if stale). It never
echo touches Penterra/Horizon client sources or your evidence.
echo.

if not exist "%~dp0runtime" (
    mkdir "%~dp0runtime"
    echo Created missing runtime\ folder.
) else (
    echo runtime\ folder present.
)

if exist "%~dp0runtime\databossx.lock" (
    set /p PID=<"%~dp0runtime\databossx.lock"
    tasklist /FI "PID eq !PID!" 2>nul | findstr /r "!PID!" >nul
    if !ERRORLEVEL! neq 0 (
        echo Clearing stale lock ^(PID !PID! is not running^).
        del "%~dp0runtime\databossx.lock" >nul 2>nul
        if exist "%~dp0runtime\port.txt" del "%~dp0runtime\port.txt" >nul 2>nul
    ) else (
        echo A server is currently running ^(PID !PID!^) -- leaving its lock in place.
        echo Run 00_STOP_DATABOSSX.bat first if you want to repair while stopped.
    )
) else (
    echo No lock file present -- nothing to reclaim.
)

if exist "%~dp0runtime\databossx.db" (
    echo Found existing database - leaving it in place ^(migrations run automatically on next start^).
) else (
    echo No database yet - one will be created cleanly on next start.
)

echo.
echo Repair complete. Run 00_START_DATABOSSX.bat next.
pause
