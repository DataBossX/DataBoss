@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime\section32_runs" (
  echo FAIL: No Section 32 run exists.
  echo Next action: run RUN_SECTION32.bat.
  exit /b 1
)
for /f "delims=" %%D in ('dir /b /ad /o-d "runtime\section32_runs"') do (
  start "" explorer "%CD%\runtime\section32_runs\%%D"
  echo PASS: Opened %%D
  exit /b 0
)
echo FAIL: No result folder was found.
exit /b 1
