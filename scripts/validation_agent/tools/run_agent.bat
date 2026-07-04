@echo off
REM DataBossX Validation Agent - run one validation from the command line
REM Usage: run_agent.bat "C:\path\to\workbook.xlsx"
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"
set "VPY=%AGENT_ROOT%\.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo BLOCKER: .venv missing. Run tools\setup_windows.bat first.
  popd & endlocal & exit /b 1
)
if "%~1"=="" (
  echo Usage: run_agent.bat "path\to\workbook.xlsx"
  popd & endlocal & exit /b 2
)
"%VPY%" "%AGENT_ROOT%\tools\run_agent_cli.py" %*
set RC=%ERRORLEVEL%
popd
endlocal & exit /b %RC%
