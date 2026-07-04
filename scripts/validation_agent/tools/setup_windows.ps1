# DataBossX Validation Agent — Windows setup (PowerShell)
# Detects Python 3.11+/3.12+, creates a local venv, installs pinned deps,
# writes .env.example, validates imports, runs healthcheck and tests.
# Never prints or stores secrets.

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
            if ($ver -match "3\.(1[1-9]|[2-9]\d)") { return $cmd }
        } catch {}
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "Python 3.11+ not found. Attempting winget install..." -ForegroundColor Yellow
    try {
        winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
        $py = "py -3.12"
    } catch {
        Write-Host "winget install failed. Install Python 3.12 manually from python.org." -ForegroundColor Red
        exit 1
    }
}
Write-Host "Using Python: $py"

$venv = Join-Path $AgentRoot ".venv"
if (-not (Test-Path $venv)) {
    $parts = $py.Split(" ")
    & $parts[0] $parts[1..($parts.Length-1)] -m venv $venv
}
$vpy = Join-Path $venv "Scripts\python.exe"

& $vpy -m pip install --upgrade pip
& $vpy -m pip install -r (Join-Path $AgentRoot "requirements-dev.txt")

if (-not (Test-Path (Join-Path $AgentRoot ".env"))) {
    Copy-Item (Join-Path $AgentRoot ".env.example") (Join-Path $AgentRoot ".env")
    Write-Host "Created .env from .env.example (edit it to add credentials; secrets never printed)."
}

Write-Host "Validating imports + healthcheck..." -ForegroundColor Cyan
& $vpy (Join-Path $AgentRoot "tools\healthcheck.py")

Write-Host "Running tests..." -ForegroundColor Cyan
& $vpy -m pytest (Join-Path $AgentRoot "tests") -q

Write-Host "Setup complete." -ForegroundColor Green
