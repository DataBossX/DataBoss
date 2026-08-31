@echo off
REM ---------------------------------------------------------------------------
REM DataBossX Control Tower - Windows entry point
REM
REM Usage:
REM   run_control_tower.bat selftest
REM   run_control_tower.bat canary
REM   run_control_tower.bat audit
REM
REM Exit codes:
REM   0  all checks passed / audit complete
REM   1  a check failed - STOP, do not claim
REM   2  audit ran but could not see its target (PARTIAL_HOST_MISMATCH)
REM
REM This entry point never claims the queue, never mutates a workbook, and
REM never removes the HOLD. Claiming is a separate deliberate step.
REM
REM RELEASE STATE: FOR REVIEW - HOLD NO EXTERNAL RELEASE
REM ---------------------------------------------------------------------------
setlocal

set "REPO_ROOT=%~dp0"
pushd "%REPO_ROOT%"

if "%~1"=="" (
  echo Usage: run_control_tower.bat [selftest^|canary^|audit]
  popd
  endlocal
  exit /b 1
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  set "PY_CMD=py -3"
) else (
  set "PY_CMD=python"
)

%PY_CMD% -m control_tower.cli %*
set "RC=%ERRORLEVEL%"

popd
endlocal & exit /b %RC%
