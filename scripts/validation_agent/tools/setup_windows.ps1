<#  DataBossX Validation Agent - Windows setup (PowerShell).
    Detects Python 3.11+/3.12+, installs via winget if missing, creates .venv,
    installs pinned deps, generates .env from .env.example, verifies imports.
    Never prints secrets. Stops with a clear message on any hard blocker.
#>
$ErrorActionPreference = "Stop"
$AgentRoot = Split-Path -Parent $PSScriptRoot
Set-Location $AgentRoot
Write-Host "== DataBossX Validation Agent setup ==" -ForegroundColor Cyan
Write-Host "Agent root: $AgentRoot"

function Find-Python {
    foreach ($cmd in @("py -3.12","py -3.11","python","python3")) {
        try {
            $parts = $cmd.Split(" ")
            $ver = & $parts[0] $parts[1..($parts.Length-1)] --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $ver -match "3\.(1[1-9]|[2-9][0-9])") { return $cmd }
        } catch {}
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "Python 3.11+ not found. Attempting winget install..." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
        $py = Find-Python
    }
}
if (-not $py) {
    Write-Host "BLOCKER: Python 3.11+ is not installed and could not be installed via winget." -ForegroundColor Red
    Write-Host "Fix: install Python 3.12 from https://www.python.org/downloads/ then re-run." -ForegroundColor Red
    exit 2
}
Write-Host "Using Python: $py"

$parts = $py.Split(" ")
& $parts[0] $parts[1..($parts.Length-1)] -m venv "$AgentRoot\.venv"
$venvPy = "$AgentRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Write-Host "BLOCKER: venv creation failed." -ForegroundColor Red; exit 3 }

& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r "$AgentRoot\requirements-dev.txt"

if (-not (Test-Path "$AgentRoot\.env")) {
    Copy-Item "$AgentRoot\.env.example" "$AgentRoot\.env"
    Write-Host "Created .env from template. Fill in credentials to enable live mode." -ForegroundColor Green
}

Write-Host "Verifying module imports..."
& $venvPy -c "import sys; sys.path.insert(0,r'$AgentRoot'); import config.settings, db.db_client, core.orchestrator, app.dashboard; print('imports OK')"
Write-Host "Setup complete. Run tools\launch_dashboard.bat to start." -ForegroundColor Green
