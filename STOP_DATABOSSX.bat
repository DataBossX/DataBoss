@echo off
setlocal
taskkill /FI "WINDOWTITLE eq DataBossX Watcher" /T /F >nul 2>&1
if errorlevel 1 (
  echo PASS: No DataBossX watcher was running.
) else (
  echo PASS: DataBossX watcher stopped.
)
exit /b 0
