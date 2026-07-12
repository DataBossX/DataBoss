@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Run SETUP_DATABOSS_TITLE_FACTORY.bat first.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :failed

if not exist "databoss_title_factory\logs" mkdir "databoss_title_factory\logs"
echo Running source-safety, provenance, reconciliation, resume, and workbook fixture tests...
python -m pytest "tests\test_databoss_title_factory.py" -v --junitxml="databoss_title_factory\logs\test_results.xml"
if errorlevel 1 goto :failed

echo.
echo All DataBoss Title Factory tests passed.
echo Test report: databoss_title_factory\logs\test_results.xml
pause
exit /b 0

:failed
echo.
echo TESTS FAILED. No production export should be submitted.
pause
exit /b 1
