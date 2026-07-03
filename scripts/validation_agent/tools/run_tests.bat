@echo off
REM DataBossX Validation Agent - run the test suite with coverage
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo .venv not found. Run tools\setup_windows.bat first.
    goto :done
)
call ".venv\Scripts\activate.bat"

python -m pytest tests -v --cov=. --cov-report=term-missing

:done
popd
endlocal
