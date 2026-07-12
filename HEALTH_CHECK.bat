@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1 || (
  echo FAIL: Python was not found. Install Python 3.10 or newer.
  exit /b 1
)
py -m core.cli --runtime runtime health
if errorlevel 1 (
  echo FAIL: Health validation failed. Review the message above.
  exit /b 1
)
echo PASS: Local kernel health validation completed.
exit /b 0
