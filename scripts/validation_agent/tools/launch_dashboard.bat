@echo off
REM Launch the DataBossX Validation Agent dashboard.
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo .venv not found. Running setup first...
  call "%~dp0setup_windows.bat"
)
call ".venv\Scripts\activate.bat"
if exist ".env" ( for /f "usebackq tokens=*" %%L in (".env") do set "%%L" )
echo Running healthcheck...
python "tools\healthcheck.py"
echo Starting dashboard at http://localhost:8501 ...
start "" http://localhost:8501
python -m streamlit run "app\dashboard.py" --server.headless true --server.port 8501
