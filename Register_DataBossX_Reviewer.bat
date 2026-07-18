@echo off
setlocal
title DataBossX Reviewer Enrollment
cd /d "%~dp0"

if not exist ".venv-kernel\Scripts\python.exe" (
  echo DataBossX is not set up yet. Run Run_DataBossX.bat first.
  pause
  exit /b 1
)

echo Reviewer enrollment runs only from this local Windows console.
echo Browser sessions cannot create reviewer credentials.
echo.
set /p "REVIEWER_NAME=Qualified examiner or attorney name: "
echo 1. Qualified examiner
echo 2. Attorney
set /p "ROLE_CHOICE=Choose role [1-2]: "
if "%ROLE_CHOICE%"=="2" (
  set "REVIEWER_ROLE=ATTORNEY"
) else (
  set "REVIEWER_ROLE=QUALIFIED_EXAMINER"
)

".venv-kernel\Scripts\python.exe" run_databossx.py reviewer-add --name "%REVIEWER_NAME%" --role "%REVIEWER_ROLE%"
if errorlevel 1 (
  echo.
  echo Reviewer enrollment failed. No approval credential was created.
  pause
  exit /b 1
)

echo.
echo Reviewer enrolled. Copy the reviewer ID into the Command Center.
pause
