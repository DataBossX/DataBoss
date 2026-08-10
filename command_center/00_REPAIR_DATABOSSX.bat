@echo off
title DataBossX Command Center - Repair
cd /d "%~dp0"
echo ============================================
echo   DataBossX Command Center - Safe Repair
echo ============================================
echo This only touches files DataBossX itself created
echo (runtime\ folder, stale PID marker). It never touches
echo Penterra/Horizon client sources or your evidence.
echo.

if not exist "%~dp0runtime" (
    mkdir "%~dp0runtime"
    echo Created missing runtime\ folder.
) else (
    echo runtime\ folder present.
)

if exist "%~dp0runtime\databossx.pid" (
    del "%~dp0runtime\databossx.pid"
    echo Cleared stale PID marker.
)

if exist "%~dp0runtime\databossx.db" (
    echo Found existing database - leaving it in place ^(migrations run automatically on next start^).
) else (
    echo No database yet - one will be created cleanly on next start.
)

echo.
echo Repair complete. Run 00_START_DATABOSSX.bat next.
pause
