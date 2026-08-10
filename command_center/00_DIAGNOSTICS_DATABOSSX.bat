@echo off
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
echo -- Project roots --
if exist "C:\DataBoss\Penterra" (echo C:\DataBoss\Penterra: FOUND) else (echo C:\DataBoss\Penterra: not found - set DATABOSSX_PENTERRA_ROOT if it lives elsewhere)
if exist "C:\DataBoss\Horizon" (echo C:\DataBoss\Horizon: FOUND) else (echo C:\DataBoss\Horizon: not found - set DATABOSSX_HORIZON_ROOT if it lives elsewhere)
echo.
echo -- Server health check (only works while the server is running) --
curl -s http://127.0.0.1:8765/api/health 2>nul
if errorlevel 1 (
    echo Could not reach http://127.0.0.1:8765 - server may not be running, or is on a different auto-selected port. Check runtime\server.log.
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
