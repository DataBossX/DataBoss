@echo off
title DataBossX Command Center - Stop
cd /d "%~dp0"
echo Stopping DataBossX Command Center...

rem Only ever targets processes running our own server.py from this folder --
rem never a blanket "taskkill python" (that would risk killing unrelated work).
wmic process where "CommandLine like '%%server.py%%' and CommandLine like '%%DataBossCommandCenter%%'" get ProcessId 2>nul | findstr /r "[0-9]" > "%TEMP%\dbx_pids.txt"

set FOUND=0
for /f %%p in ('type "%TEMP%\dbx_pids.txt" 2^>nul') do (
    set FOUND=1
    echo Stopping PID %%p
    taskkill /PID %%p /F >nul 2>nul
)
del "%TEMP%\dbx_pids.txt" >nul 2>nul

if "%FOUND%"=="0" (
    echo No running DataBossX Command Center server was found.
) else (
    echo Done.
)
if exist "%~dp0runtime\databossx.pid" del "%~dp0runtime\databossx.pid" >nul 2>nul
pause
