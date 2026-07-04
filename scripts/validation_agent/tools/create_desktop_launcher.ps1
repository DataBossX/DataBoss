# DataBossX Validation Agent — create the Desktop launcher.
# Writes "DataBossX Validation Agent.bat" to the user's Desktop (the ONLY file
# permitted outside the module folder). Logs the event; never overwrites the
# module's own files. If the Desktop is not writable, prints a clear blocker.

$ErrorActionPreference = "Stop"
$AgentRoot = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath("Desktop")
if (-not (Test-Path $Desktop)) {
    Write-Host "BLOCKER: Desktop folder not found at $Desktop" -ForegroundColor Red
    exit 1
}
$LauncherPath = Join-Path $Desktop "DataBossX Validation Agent.bat"
$Target = Join-Path $AgentRoot "tools\launch_dashboard.bat"

$content = @"
@echo off
REM DataBossX Validation Agent desktop launcher (auto-generated)
call "$Target"
"@

try {
    Set-Content -Path $LauncherPath -Value $content -Encoding ASCII
    Write-Host "Desktop launcher created: $LauncherPath" -ForegroundColor Green
} catch {
    Write-Host "BLOCKER: could not write Desktop launcher: $_" -ForegroundColor Red
    exit 1
}

# Log the launcher creation into the append-only DB (best-effort).
$vpy = Join-Path $AgentRoot ".venv\Scripts\python.exe"
if (Test-Path $vpy) {
    & $vpy -c "import sys; sys.path.insert(0, r'$AgentRoot'); from config.settings import load_settings; from db.db_client import DatabaseManager; s=load_settings(); s.ensure_dirs(); DatabaseManager(s.db_path).insert('launcher_events', {'event':'desktop_launcher_created','detail': r'$LauncherPath'}); print('logged')"
}
