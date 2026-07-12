@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime\command_center" mkdir "runtime\command_center"
start "" explorer "%CD%\runtime\command_center"
if errorlevel 1 (
  echo FAIL: Could not open the command-center folder.
  exit /b 1
)
echo PASS: Command-center folder opened.
exit /b 0
