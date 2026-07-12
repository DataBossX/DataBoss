@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1 || (
  echo FAIL: Python was not found. Install Python 3.10 or newer, then retry.
  exit /b 1
)
if not exist "runtime\command_center" mkdir "runtime\command_center"
start "DataBossX Watcher" /min cmd /c "for /L %%G in (0,0,1) do @(py -m core.cli --runtime runtime process-once ^& timeout /t 5 /nobreak ^>nul)"
echo PASS: DataBossX watcher started with a five-second polling interval.
echo Next action: place only schema-valid JSON jobs in runtime\command_center\inbox.
exit /b 0
