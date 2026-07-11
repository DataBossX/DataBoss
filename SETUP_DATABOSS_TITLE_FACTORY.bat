@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "databoss_title_factory\logs" mkdir "databoss_title_factory\logs"
set "SETUP_LOG=databoss_title_factory\logs\setup_%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%.log"
set "SETUP_LOG=%SETUP_LOG: =0%"

echo DATABOSS TITLE FACTORY SETUP
echo DATABOSS TITLE FACTORY SETUP>"%SETUP_LOG%"
echo --------------------------------

where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python Launcher for Windows was not found.
  echo ERROR: Python Launcher not found.>>"%SETUP_LOG%"
  goto :failed
)

for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE (
  for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
)
if not defined PYTHON_EXE (
  echo ERROR: Python 3.11 or newer was not found.
  echo ERROR: Compatible Python not found.>>"%SETUP_LOG%"
  goto :failed
)

echo Selected Python: "%PYTHON_EXE%"
"%PYTHON_EXE%" --version
echo Selected Python: "%PYTHON_EXE%">>"%SETUP_LOG%"
"%PYTHON_EXE%" --version >>"%SETUP_LOG%" 2>&1

if not exist ".venv\Scripts\python.exe" (
  echo Creating isolated .venv...
  "%PYTHON_EXE%" -m venv ".venv" >>"%SETUP_LOG%" 2>&1
  if errorlevel 1 goto :failed
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :failed

echo Updating pip inside .venv only...
python -m pip install --upgrade pip setuptools wheel >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :failed

echo Installing pinned dependencies...
python -m pip install --requirement "databoss_title_factory\requirements.txt" >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :failed

where tesseract >nul 2>nul
if errorlevel 1 (
  echo WARNING: Tesseract was not found. Image OCR remains blocked.
  echo WARNING: Tesseract not found.>>"%SETUP_LOG%"
) else (
  for /f "delims=" %%T in ('where tesseract') do echo Tesseract: %%T
)

where git >nul 2>nul
if errorlevel 1 (
  echo WARNING: Git was not found.
  echo WARNING: Git not found.>>"%SETUP_LOG%"
) else (
  for /f "delims=" %%G in ('where git') do echo Git: %%G
)

reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\excel.exe" >nul 2>nul
if errorlevel 1 (
  reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\excel.exe" >nul 2>nul
)
if errorlevel 1 (
  echo WARNING: Microsoft Excel was not detected. High-risk workbook editing must remain blocked.
  echo WARNING: Microsoft Excel not detected.>>"%SETUP_LOG%"
) else (
  echo Microsoft Excel detected.
  echo Microsoft Excel detected.>>"%SETUP_LOG%"
)

echo Running smoke test...
python -c "import streamlit, openpyxl, fitz, PIL, pytesseract, pydantic, cv2; from databoss_title_factory.workbook_audit import audit_workbook; print('Smoke test passed')" >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto :failed

echo.
echo Setup complete. Log: %SETUP_LOG%
echo Run RUN_DATABOSS_TITLE_FACTORY.bat next.
pause
exit /b 0

:failed
echo.
echo SETUP FAILED. Review: %SETUP_LOG%
echo No source project files were modified.
pause
exit /b 1
