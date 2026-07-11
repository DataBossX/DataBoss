@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo DataBoss Title Factory is not set up yet.
  echo Running setup first...
  call "Setup_DataBoss_Title_Factory.bat"
  if errorlevel 1 exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo ERROR: Could not activate the local virtual environment.
  pause
  exit /b 1
)

echo Starting DataBoss Title Factory at http://localhost:8501
python -m streamlit run "databoss_title_factory\app.py" --server.address localhost --server.port 8501

if errorlevel 1 (
  echo.
  echo The app stopped with an error.
  pause
)
