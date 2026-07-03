<#
    DataBossX Validation Agent - Windows setup (PowerShell)
    - Detects Python 3.11+/3.12+, installs via winget if missing.
    - Creates .venv and installs pinned dependencies.
    - Generates .env from .env.example if absent.
    - Validates that all modules import.
    Never prints secrets. Never installs unpinned packages.
#>
$ErrorActionPreference = "Stop"
$AgentRoot = Split-Path -Parent $PSScriptRoot
Set-Location $AgentRoot
Write-Host "== DataBossX Validation Agent setup ==" -ForegroundColor Cyan
Write-Host "Agent root: $AgentRoot"

function Find-Python {
    foreach ($cmd in @("py -3.12", "py -3.11", "python", "python3")) {
        try {
            $parts = $cmd.Split(" ")
            $ver = & $parts[0] $parts[1..($parts.Length-1)] --version 2>&1
            if ($ver -match "Python 3\.(1[1-9]|[2-9]\d)") { return $cmd }
        } catch { }
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "Python 3.11+ not found. Attempting winget install..." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        $py = Find-Python
    }
    if (-not $py) {
        Write-Host "BLOCKER: Could not install Python automatically." -ForegroundColor Red
        Write-Host "Install Python 3.12 from https://www.python.org/downloads/ and re-run." -ForegroundColor Red
        exit 1
    }
}
Write-Host "Using Python: $py"

$parts = $py.Split(" ")
$venv = Join-Path $AgentRoot ".venv"
if (-not (Test-Path $venv)) {
    & $parts[0] $parts[1..($parts.Length-1)] -m venv $venv
}
$venvPy = Join-Path $venv "Scripts\python.exe"

& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r (Join-Path $AgentRoot "requirements-dev.txt")

$envFile = Join-Path $AgentRoot ".env"
$envExample = Join-Path $AgentRoot ".env.example"
if ((-not (Test-Path $envFile)) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host "Created .env from template. Fill in credentials before live mode." -ForegroundColor Yellow
}

Write-Host "Validating module imports..."
& $venvPy -c "import sys; sys.path.insert(0,r'$AgentRoot'); import config.settings, db.db_client, core.orchestrator, app.dashboard; print('Imports OK')"

Write-Host "Running healthcheck..."
& $venvPy (Join-Path $AgentRoot "tools\healthcheck.py")

Write-Host "Setup complete." -ForegroundColor Green
