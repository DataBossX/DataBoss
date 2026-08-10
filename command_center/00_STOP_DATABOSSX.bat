@echo off
setlocal enabledelayedexpansion
title DataBossX Command Center - Stop
cd /d "%~dp0"
echo Stopping DataBossX Command Center...

rem Identity comes ONLY from runtime\databossx.lock -- the PID the server
rem itself wrote at startup. We never guess by process name; a Python
rem process that happens to be running something else is left alone.
if not exist "%~dp0runtime\databossx.lock" (
    echo No lock file found -- no DataBossX Command Center server appears to be running.
    pause
    exit /b 0
)

set /p PID=<"%~dp0runtime\databossx.lock"

rem Verify the PID is actually alive AND is a python process before touching it.
set IS_PYTHON=0
for /f "tokens=1" %%n in ('tasklist /FI "PID eq %PID%" /FO CSV /NH 2^>nul') do (
    echo %%n | findstr /i "python" >nul && set IS_PYTHON=1
)

tasklist /FI "PID eq %PID%" 2>nul | findstr /r "%PID%" >nul
if %ERRORLEVEL% neq 0 (
    echo Lock file points at PID %PID%, but that process is not running ^(stale lock^).
    del "%~dp0runtime\databossx.lock" >nul 2>nul
    if exist "%~dp0runtime\port.txt" del "%~dp0runtime\port.txt" >nul 2>nul
    echo Cleared stale lock. Nothing to stop.
    pause
    exit /b 0
)

if "%IS_PYTHON%"=="0" (
    echo [SAFETY] PID %PID% is running but is NOT a python.exe/pythonw.exe process.
    echo Refusing to kill it -- this would not be our server. Investigate manually.
    pause
    exit /b 1
)

echo Stopping PID %PID% ^(verified python process^)...
taskkill /PID %PID% /F >nul 2>nul

del "%~dp0runtime\databossx.lock" >nul 2>nul
if exist "%~dp0runtime\port.txt" del "%~dp0runtime\port.txt" >nul 2>nul
echo Done.
pause
