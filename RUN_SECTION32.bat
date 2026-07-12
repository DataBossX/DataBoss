@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1 || (
  echo FAIL: Python was not found. Install Python 3.10 or newer.
  exit /b 1
)
py -m core.cli --runtime runtime run-section32
if errorlevel 2 (
  echo PARTIAL: A source-limited HOLD_NO_RELEASE package was created.
  echo Next action: mount the private Section 32 corpus and controlling template read-only.
  exit /b 2
)
if errorlevel 1 (
  echo FAIL: Section 32 execution failed. Review the console output.
  exit /b 1
)
echo PASS: Section 32 execution completed.
exit /b 0
