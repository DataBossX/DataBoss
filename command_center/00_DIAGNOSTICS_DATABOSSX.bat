@echo off
setlocal enabledelayedexpansion
title DataBossX Command Center - Diagnostics
cd /d "%~dp0"
echo ============================================
echo   DataBossX Command Center - Diagnostics
echo ============================================
echo.
echo -- Python --
where python 2>nul
where py 2>nul
python --version 2>nul
echo.
echo -- Files --
if exist server.py (echo server.py: OK) else (echo server.py: MISSING)
if exist static\index.html (echo static\index.html: OK) else (echo static\index.html: MISSING)
if exist runtime\databossx.db (echo runtime\databossx.db: OK) else (echo runtime\databossx.db: not yet created - normal on first run)
echo.
echo -- Server identity --
set PID=
set PORT=
if exist runtime\databossx.lock (
    set /p PID=<runtime\databossx.lock
    echo Lock file PID: !PID!
    tasklist /FI "PID eq !PID!" 2>nul | findstr /r "!PID!" >nul
    if !ERRORLEVEL!==0 (echo   -> alive) else (echo   -> STALE, not running)
) else (
    echo No lock file - server not started, or was stopped cleanly.
)
if exist runtime\port.txt (
    set /p PORT=<runtime\port.txt
    echo Reported port: !PORT!
) else (
    echo No port.txt yet.
)
echo.
echo -- Project roots --
if exist "C:\DataBoss\Penterra" (echo C:\DataBoss\Penterra: FOUND) else (echo C:\DataBoss\Penterra: not found - set DATABOSSX_PENTERRA_ROOT if it lives elsewhere)
if exist "C:\DataBoss\Horizon" (echo C:\DataBoss\Horizon: FOUND) else (echo C:\DataBoss\Horizon: not found - set DATABOSSX_HORIZON_ROOT if it lives elsewhere)
echo.
echo -- Server health check --
if not "!PORT!"=="" (
    curl -s http://127.0.0.1:!PORT!/api/health 2>nul
    if errorlevel 1 echo Could not reach http://127.0.0.1:!PORT! -- check runtime\server.log.
) else (
    echo Skipped - no known port yet.
)
echo.
echo -- Last 20 lines of server.log --
if exist runtime\server.log (
    powershell -command "Get-Content runtime\server.log -Tail 20"
) else (
    echo No server.log yet.
)
echo.
pause
