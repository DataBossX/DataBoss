@echo off
REM Run one validation pass headlessly: run_agent.bat "C:\path\to\workbook.xlsx" "Prospect"
setlocal
cd /d "%~dp0.."
call ".venv\Scripts\activate.bat"
if exist ".env" ( for /f "usebackq tokens=*" %%L in (".env") do set "%%L" )
python -c "import sys; sys.path.insert(0,'.'); from pathlib import Path; from config.settings import get_settings; from db.db_client import DatabaseManager; from db.audit_logger import AuditLogger; from core.orchestrator import Orchestrator; s=get_settings(reload=True); db=DatabaseManager(s.db_path,s.schema_path); a=AuditLogger(db); r=Orchestrator(s,db,a).run(Path(sys.argv[1]), prospect=(sys.argv[2] if len(sys.argv)>2 else '')); print('FINAL:', r['final_status'], r['run_id']); db.close()" %*
pause
