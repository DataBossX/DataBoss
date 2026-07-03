@echo off
REM DataBossX Validation Agent - run a single validation from the CLI
REM Usage: run_agent.bat "C:\path\to\workbook.xlsx" [--approve-paid]
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo .venv not found. Run tools\setup_windows.bat first.
    goto :done
)
call ".venv\Scripts\activate.bat"

if "%~1"=="" (
    echo Usage: run_agent.bat "path\to\workbook.xlsx" [--approve-paid]
    goto :done
)

python tools\run_agent.py %*

:done
popd
endlocal
