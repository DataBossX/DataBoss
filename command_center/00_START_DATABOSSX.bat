@echo off
setlocal enabledelayedexpansion
title DataBossX Command Center
cd /d "%~dp0"

echo ============================================
echo   DataBossX Command Center - Starting
echo ============================================

rem --- 1. Find the app: confirm server.py is where we expect it ---
if not exist "%~dp0server.py" (
    echo [ERROR] server.py not found next to this launcher.
    echo Expected it at: %~dp0server.py
    pause
    exit /b 1
)

rem --- 2. Fast preflight: find a working Python ---
set PY_CMD=
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set PY_CMD=py
) else (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
        set PY_CMD=python
    )
)
if "%PY_CMD%"=="" (
    echo [ERROR] No Python interpreter found on PATH.
    echo Install Python 3.10+ from https://python.org and re-run this launcher.
    pause
    exit /b 1
)

rem --- 3. Use existing venv when healthy, else run on system Python ---
rem The Command Center is stdlib-only by design, so a venv is optional.
if exist "%~dp0.venv\Scripts\python.exe" (
    set PY_CMD="%~dp0.venv\Scripts\python.exe"
)

rem --- 4/5. Minimum runtime dirs + SQLite live under command_center\runtime ---
if not exist "%~dp0runtime" mkdir "%~dp0runtime"

rem --- 6. Stale-PID self-heal: clear a leftover lock from a crashed run ---
if exist "%~dp0runtime\databossx.pid" del "%~dp0runtime\databossx.pid" >nul 2>nul

rem --- 7/8/9. Start exactly one instance, then open the browser ---
echo Starting server...
start "DataBossX Command Center Server" /min cmd /c "%PY_CMD% server.py > runtime\server.log 2>&1"

echo %RANDOM% > "%~dp0runtime\databossx.pid"
timeout /t 2 /nobreak >nul

for /f "tokens=2 delims=:" %%p in ('findstr /r "127.0.0.1:[0-9]*" "%~dp0runtime\server.log" 2^>nul') do (
    echo Server appears to be starting on port%%p
)

echo Opening browser at http://127.0.0.1:8765 ...
start http://127.0.0.1:8765/

echo.
echo If the browser shows nothing, check runtime\server.log for the actual
echo port (it auto-selects a free loopback port starting at 8765) and open
echo that address manually. This window can be closed.
pause
