@echo off
REM Run the validation agent headlessly against a workbook.
REM Usage: run_agent.bat "C:\path\to\workbook.xlsx"
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Run tools\setup_windows.bat first.
    popd & endlocal & exit /b 1
)
if "%~1"=="" (
    echo [ERROR] Provide a workbook path: run_agent.bat "C:\path\to\workbook.xlsx"
    popd & endlocal & exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m core.cli "%~1"
popd
endlocal
