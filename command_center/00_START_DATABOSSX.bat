@echo off
setlocal enabledelayedexpansion
title DataBossX Command Center
cd /d "%~dp0"

rem --- 0. Parse args: --sandbox / --sandbox-root <path> ---
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

echo ============================================
echo   DataBossX Command Center - Starting
echo ============================================

rem --- 1. Find the app: confirm server.py is where we expect it ---
if not exist "%~dp0server.py" (
    echo [ERROR] server.py not found next to this launcher.
    echo Expected it at: %~dp0server.py
    if "%NONINTERACTIVE%"=="0" pause
    exit /b 1
)

rem --- 2. Fast preflight: find a working Python. Uses !ERRORLEVEL! ^(delayed
rem     expansion^) throughout -- %ERRORLEVEL% inside a parenthesized block
rem     is expanded once, at parse time, so it can read a stale value from
rem     before the command in that same block actually ran. ---
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
    echo [ERROR] No working Python interpreter found on PATH ^(tried "py -3" and "python"^).
    echo Install Python 3.10+ from https://python.org and re-run this launcher.
    if "%NONINTERACTIVE%"=="0" pause
    exit /b 1
)

rem --- 3. Use existing venv when healthy, else run on system Python ---
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD="%~dp0.venv\Scripts\python.exe""
)

rem --- 4. Sandbox mode: synthetic roots + runtime under a fresh sandbox,
rem     never anywhere near C:\DataBoss\Penterra or C:\DataBoss\Horizon ---
if "%SANDBOX_MODE%"=="1" (
    if "%SANDBOX_ROOT%"=="" set "SANDBOX_ROOT=%LOCALAPPDATA%\DataBossX\FirstRunSandbox"
    set "RUNTIME_DIR=!SANDBOX_ROOT!\runtime"
    set "DATABOSSX_SANDBOX_MODE=1"
    set "DATABOSSX_DB_PATH=!SANDBOX_ROOT!\runtime\databossx.db"
    set "DATABOSSX_PENTERRA_ROOT=!SANDBOX_ROOT!\SyntheticPenterra"
    set "DATABOSSX_HORIZON_ROOT=!SANDBOX_ROOT!\SyntheticHorizon"
    if not exist "!SANDBOX_ROOT!" mkdir "!SANDBOX_ROOT!"
    if not exist "!DATABOSSX_PENTERRA_ROOT!" mkdir "!DATABOSSX_PENTERRA_ROOT!"
    if not exist "!DATABOSSX_HORIZON_ROOT!" mkdir "!DATABOSSX_HORIZON_ROOT!"
    if not exist "!DATABOSSX_PENTERRA_ROOT!\SyntheticProject-01" (
        mkdir "!DATABOSSX_PENTERRA_ROOT!\SyntheticProject-01"
        > "!DATABOSSX_PENTERRA_ROOT!\SyntheticProject-01\Runsheet_sample.txt" (
            echo This is a harmless synthetic sandbox file. NO CLIENT DATA.
            echo Created by 00_START_DATABOSSX.bat --sandbox for local/CI testing only.
        )
    )
    echo ============================================
    echo   SANDBOX MODE -- NO CLIENT DATA
    echo   Penterra root: !DATABOSSX_PENTERRA_ROOT!
    echo   Horizon root:  !DATABOSSX_HORIZON_ROOT!
    echo   Runtime dir:   !RUNTIME_DIR!
    echo ============================================
) else (
    set "RUNTIME_DIR=%~dp0runtime"
)

rem --- 5. Minimum runtime dirs + SQLite live under the runtime dir ---
if not exist "!RUNTIME_DIR!" mkdir "!RUNTIME_DIR!"

rem --- 6. Ask the shared identity validator (identity_cli.py -- the same
rem     module STOP/REPAIR/DIAGNOSTICS and the server's own single-instance
rem     lock use) whether a verified instance is already running. Never
rem     decide this from a bare PID/tasklist name match. ---
!PY_CMD! "%~dp0identity_cli.py" --runtime-dir "!RUNTIME_DIR!" status > "!RUNTIME_DIR!\_start_status.json" 2>nul
findstr /C:"\"status\": \"RUNNING\"" "!RUNTIME_DIR!\_start_status.json" >nul
if !ERRORLEVEL!==0 (
    echo A verified DataBossX Command Center server is already running.
    if exist "!RUNTIME_DIR!\port.txt" (
        for /f "usebackq" %%q in ("!RUNTIME_DIR!\port.txt") do set "PORT=%%q"
        echo Opening its browser tab at http://127.0.0.1:!PORT!/
        if "%NONINTERACTIVE%"=="0" start http://127.0.0.1:!PORT!/
    )
    del "!RUNTIME_DIR!\_start_status.json" >nul 2>nul
    if "%NONINTERACTIVE%"=="0" pause
    exit /b 0
)
del "!RUNTIME_DIR!\_start_status.json" >nul 2>nul
rem Not RUNNING (ABSENT/STALE/MALFORMED/MISMATCHED): reclaim any stale
rem receipt file. A MISMATCHED result means the PID belongs to an
rem unrelated live process -- repair only ever clears our OWN receipt
rem file, it never touches that process.
!PY_CMD! "%~dp0identity_cli.py" --runtime-dir "!RUNTIME_DIR!" repair >nul 2>nul
if exist "!RUNTIME_DIR!\port.txt" del "!RUNTIME_DIR!\port.txt" >nul 2>nul

rem --- 7. Start exactly one instance ---
echo Starting server...
start "DataBossX Command Center Server" /min cmd /c "!PY_CMD! server.py > "!RUNTIME_DIR!\server.log" 2>&1"

rem --- 8. Wait (bounded) for BOTH the authoritative identity receipt AND a
rem     successful /api/health response from that same instance -- never
rem     open a browser off port.txt alone. ---
set "PORT="
set "READY=0"
for /l %%i in (1,1,30) do (
    if "!READY!"=="0" (
        !PY_CMD! "%~dp0identity_cli.py" --runtime-dir "!RUNTIME_DIR!" status > "!RUNTIME_DIR!\_start_status.json" 2>nul
        findstr /C:"\"status\": \"RUNNING\"" "!RUNTIME_DIR!\_start_status.json" >nul
        if !ERRORLEVEL!==0 (
            if exist "!RUNTIME_DIR!\port.txt" (
                for /f "usebackq" %%q in ("!RUNTIME_DIR!\port.txt") do set "PORT=%%q"
                curl -s -f -o nul "http://127.0.0.1:!PORT!/api/health" >nul 2>nul
                if !ERRORLEVEL!==0 set "READY=1"
            )
        )
    )
    if "!READY!"=="0" timeout /t 1 /nobreak >nul
)
del "!RUNTIME_DIR!\_start_status.json" >nul 2>nul

if "!READY!"=="0" (
    echo [ERROR] Server did not reach a verified, healthy state within 30 seconds.
    echo Check "!RUNTIME_DIR!\server.log" for the actual failure.
    type "!RUNTIME_DIR!\server.log" 2>nul
    if "%NONINTERACTIVE%"=="0" pause
    exit /b 1
)

echo Server is up on port !PORT! ^(identity verified, /api/health OK^).
if "%SANDBOX_MODE%"=="1" (
    echo SANDBOX MODE -- NO CLIENT DATA is active for this run.
)
echo Opening http://127.0.0.1:!PORT!/ ...
if "%NONINTERACTIVE%"=="0" (
    start http://127.0.0.1:!PORT!/
) else (
    echo [noninteractive] Not opening a browser. URL: http://127.0.0.1:!PORT!/
)

echo.
echo This window can be closed. Use 00_STOP_DATABOSSX.bat to stop the server.
if "%NONINTERACTIVE%"=="0" pause
