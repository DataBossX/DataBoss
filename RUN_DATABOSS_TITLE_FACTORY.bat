@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: The local .venv does not exist.
  echo Run SETUP_DATABOSS_TITLE_FACTORY.bat first.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo ERROR: Could not activate the local virtual environment.
  pause
  exit /b 1
)

python -c "import streamlit, openpyxl, fitz, PIL, pytesseract, pydantic, cv2" >nul 2>nul
if errorlevel 1 (
  echo ERROR: Required packages are missing or damaged.
  echo Run SETUP_DATABOSS_TITLE_FACTORY.bat again.
  pause
  exit /b 1
)

echo Starting DataBoss Title Factory locally...
echo Browser URL: http://localhost:8501
python -m streamlit run "databoss_title_factory\app.py" --server.address localhost --server.port 8501 --server.headless false

if errorlevel 1 (
  echo.
  echo ERROR: The app stopped unexpectedly. Review the message above.
  pause
  exit /b 1
)
