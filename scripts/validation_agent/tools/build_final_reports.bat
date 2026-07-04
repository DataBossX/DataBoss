@echo off
REM DataBossX - build final Roger Mills cursory reports from the Horizon folders.
REM Edit the paths below if your layout differs. Sources are never overwritten.
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"
set "VPY=%AGENT_ROOT%\.venv\Scripts\python.exe"
if not exist "%VPY%" set "VPY=python"

"%VPY%" "%AGENT_ROOT%\tools\build_final_reports.py" ^
  --input "D:\Desktop\Horizon\Roger Mills" ^
  --input "D:\Desktop\Horizon\Roger Mills 2" ^
  --input "D:\Desktop\Horizon\Roger Mills 3" ^
  --out   "D:\Desktop\Horizon\rogermillsfinalreports" ^
  --env   "D:\Desktop\Horizon\.env"

set RC=%ERRORLEVEL%
popd
endlocal & exit /b %RC%
