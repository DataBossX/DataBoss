# DataBossX Foundry bootstrap — Windows 11 / PowerShell.
# Creates the Foundry venv, installs the package, and runs doctor.
# Usage:  powershell -ExecutionPolicy Bypass -File foundry\scripts\bootstrap.ps1

$ErrorActionPreference = "Stop"
$FoundryDir = Split-Path -Parent $PSScriptRoot

Write-Host "== DataBossX Foundry bootstrap ==" -ForegroundColor Cyan
Set-Location $FoundryDir

$Python = Get-Command py -ErrorAction SilentlyContinue
if ($Python) { $PythonCmd = "py" } else { $PythonCmd = "python" }

if (-not (Test-Path ".venv")) {
    Write-Host "creating venv..."
    & $PythonCmd -m venv .venv
}

$VenvPython = Join-Path $FoundryDir ".venv\Scripts\python.exe"
& $VenvPython -m pip install --quiet --upgrade pip
& $VenvPython -m pip install --quiet -e ".[dev]"

Write-Host "running doctor..." -ForegroundColor Cyan
& $VenvPython -m databossx doctor
$DoctorExit = $LASTEXITCODE

Write-Host "running test suite..." -ForegroundColor Cyan
& $VenvPython -m pytest tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($DoctorExit -ne 0) {
    Write-Host "doctor is NOT clean - run the printed install commands (or 'databossx doctor --install') and re-run." -ForegroundColor Yellow
    exit $DoctorExit
}
Write-Host "Foundry ready." -ForegroundColor Green
