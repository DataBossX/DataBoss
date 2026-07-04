@echo off
REM Run the test suite with coverage.
setlocal
set "AGENT_ROOT=%~dp0.."
pushd "%AGENT_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Run tools\setup_windows.bat first.
    popd & endlocal & exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pytest tests -v --cov=. --cov-report=term-missing
popd
endlocal
