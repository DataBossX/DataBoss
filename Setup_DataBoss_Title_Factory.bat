@echo off
setlocal
cd /d "%~dp0"

echo.
echo  DATABOSS TITLE FACTORY / SETUP
echo  --------------------------------

where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher "py" was not found.
  echo Install Python 3.10 or newer from https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 goto :failed
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :failed

echo Updating packaging tools...
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :failed

echo Installing DataBoss Title Factory...
python -m pip install --upgrade -r "databoss_title_factory\requirements.txt"
if errorlevel 1 goto :failed

where tesseract >nul 2>nul
if errorlevel 1 (
  echo.
  echo NOTE: The Python app is installed, but the Tesseract OCR program was not found.
  echo Install Tesseract for Windows and add it to PATH before using image OCR.
  echo Native PDF, workbook, CSV, and text extraction will still work.
)

echo.
echo Setup complete. The virtual environment is active for this window.
echo Next time, double-click Run_DataBoss_Title_Factory.bat.
pause
exit /b 0

:failed
echo.
echo SETUP FAILED. Review the error above; no project source files were changed.
pause
exit /b 1
