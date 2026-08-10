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

rem --- 6. Refuse a second instance up front (the server also enforces this
rem     itself via runtime\databossx.lock -- this is just a friendlier message) ---
if exist "%~dp0runtime\databossx.lock" (
    for /f "usebackq" %%p in ("%~dp0runtime\databossx.lock") do set EXISTING_PID=%%p
    tasklist /FI "PID eq !EXISTING_PID!" 2>nul | findstr /i "!EXISTING_PID!" >nul
    if !ERRORLEVEL!==0 (
        echo A DataBossX Command Center server already appears to be running ^(PID !EXISTING_PID!^).
        if exist "%~dp0runtime\port.txt" (
            for /f "usebackq" %%q in ("%~dp0runtime\port.txt") do set EXISTING_PORT=%%q
            echo Opening its browser tab at http://127.0.0.1:!EXISTING_PORT!/
            start http://127.0.0.1:!EXISTING_PORT!/
        )
        pause
        exit /b 0
    ) else (
        echo Found a stale lock from a crashed run -- clearing it.
        del "%~dp0runtime\databossx.lock" >nul 2>nul
    )
)
if exist "%~dp0runtime\port.txt" del "%~dp0runtime\port.txt" >nul 2>nul

rem --- 7/8. Start exactly one instance ---
echo Starting server...
start "DataBossX Command Center Server" /min cmd /c "%PY_CMD% server.py > runtime\server.log 2>&1"

rem --- 9. Wait (bounded) for the server to publish its real port, then open
rem     exactly that URL -- never a hard-coded guess ---
set PORT=
for /l %%i in (1,1,20) do (
    if exist "%~dp0runtime\port.txt" (
        for /f "usebackq" %%q in ("%~dp0runtime\port.txt") do set PORT=%%q
        goto :got_port
    )
    timeout /t 1 /nobreak >nul
)
:got_port

if "%PORT%"=="" (
    echo [ERROR] Server did not report a port within 20 seconds.
    echo Check runtime\server.log for the actual failure.
    type "%~dp0runtime\server.log" 2>nul
    pause
    exit /b 1
)

echo Server is up on port %PORT%.
echo Opening http://127.0.0.1:%PORT%/ ...
start http://127.0.0.1:%PORT%/

echo.
echo This window can be closed. Use 00_STOP_DATABOSSX.bat to stop the server.
pause
