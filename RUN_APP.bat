@echo off
REM Start the DataBossX FastAPI backend (http://localhost:8001).
REM Make sure backend\.env exists (copy from backend\.env.example) and that
REM dependencies are installed: pip install -r requirements.txt
cd /d "%~dp0backend"
python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload
pause
