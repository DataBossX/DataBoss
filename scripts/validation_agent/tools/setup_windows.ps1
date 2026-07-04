# DataBossX Validation Agent — Windows setup (PowerShell)
# Detects Python 3.11+/3.12+, installs via winget if missing, creates a local
# .venv, installs pinned deps, generates .env, and validates imports.
# Never prints secrets. Stops with a clear message on any blocker.

$ErrorActionPreference = "Stop"
$AgentRoot = Split-Path -Parent $PSScriptRoot
Set-Location $AgentRoot
Write-Host "== DataBossX Validation Agent setup ==" -ForegroundColor Cyan
Write-Host "Agent root: $AgentRoot"

function Get-Python {
    foreach ($cmd in @("py -3.12", "py -3.11", "python", "python3")) {
        try {
            $parts = $cmd.Split(" ")
            $ver = & $parts[0] $parts[1..($parts.Length-1)] --version 2>&1
            if ($ver -match "Python 3\.(1[1-9]|[2-9]\d)") { return $cmd }
        } catch { }
    }
    return $null
}

$py = Get-Python
if (-not $py) {
    Write-Host "Python 3.11+ not found. Attempting winget install..." -ForegroundColor Yellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Host "BLOCKER: winget is unavailable. Install Python 3.12 manually from python.org, then re-run." -ForegroundColor Red
        exit 1
    }
    winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
    $py = Get-Python
    if (-not $py) {
        Write-Host "BLOCKER: Python still not detected after winget install. Open a new shell and re-run." -ForegroundColor Red
        exit 1
    }
}
Write-Host "Using Python: $py"

# Create venv
$venv = Join-Path $AgentRoot ".venv"
if (-not (Test-Path $venv)) {
    $parts = $py.Split(" ")
    & $parts[0] $parts[1..($parts.Length-1)] -m venv $venv
}
$vpy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $vpy)) { Write-Host "BLOCKER: venv creation failed." -ForegroundColor Red; exit 1 }

# Upgrade pip and install pinned deps only
& $vpy -m pip install --upgrade pip
& $vpy -m pip install -r (Join-Path $AgentRoot "requirements-dev.txt")

# Generate .env from example if missing (never overwrite an existing .env)
$envFile = Join-Path $AgentRoot ".env"
$envExample = Join-Path $AgentRoot ".env.example"
if ((-not (Test-Path $envFile)) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host "Created .env from .env.example (fill in credentials; secrets never printed)."
}

# Validate imports
& $vpy -c "import openpyxl, lxml, pydantic, streamlit, reportlab, docx, rapidfuzz; print('imports OK')"
Write-Host "Setup complete. Next: tools\run_tests.bat then tools\launch_dashboard.bat" -ForegroundColor Green
