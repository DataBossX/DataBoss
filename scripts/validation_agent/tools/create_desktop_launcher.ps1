# Create the Windows Desktop launcher for the DataBossX Validation Agent.
# Produces "DataBossX Validation Agent.bat" on the current user's Desktop.
# If run in a cloud/repo environment without a Desktop, it writes the launcher
# into tools/ and records that the desktop shortcut must be created locally.

$ErrorActionPreference = "Stop"
$AgentRoot = Split-Path -Parent $PSScriptRoot
$LauncherName = "DataBossX Validation Agent.bat"

$LauncherBody = @"
@echo off
REM DataBossX Validation Agent desktop launcher
setlocal
set "AGENT_ROOT=$AgentRoot"
pushd "%AGENT_ROOT%"
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Dependencies missing. Open a terminal in:
    echo   %AGENT_ROOT%
    echo and run: tools\setup_windows.bat
    pause
    popd ^& endlocal ^& exit /b 1
)
call ".venv\Scripts\activate.bat"
python tools\healthcheck.py
python -c "import sys; sys.path.insert(0,'.'); from config.settings import load_settings; from db.db_client import DatabaseManager; from db.audit_logger import AuditLogger; s=load_settings(); d=DatabaseManager(s.db_path); d.initialize_schema(); AuditLogger(d).log_launcher_event('desktop_launch','launched'); d.close()"
start "" http://localhost:8501
python -m streamlit run app\dashboard.py
popd
endlocal
"@

$Desktop = [Environment]::GetFolderPath("Desktop")
if ($Desktop -and (Test-Path $Desktop)) {
    $Target = Join-Path $Desktop $LauncherName
    Set-Content -Path $Target -Value $LauncherBody -Encoding ASCII
    Write-Host "Created desktop launcher: $Target" -ForegroundColor Green
} else {
    $Fallback = Join-Path $AgentRoot ("tools\" + $LauncherName)
    Set-Content -Path $Fallback -Value $LauncherBody -Encoding ASCII
    Write-Host "No Desktop found (cloud/repo environment)." -ForegroundColor Yellow
    Write-Host "Launcher written to: $Fallback" -ForegroundColor Yellow
    Write-Host "Run this script locally on Windows to place it on your Desktop."
}
