# Create a Desktop launcher: "DataBossX Validation Agent.bat"
$ErrorActionPreference = "Stop"
$AgentRoot = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath("Desktop")
$Launcher = Join-Path $Desktop "DataBossX Validation Agent.bat"
$content = "@echo off`r`ncall `"$AgentRoot\tools\launch_dashboard.bat`"`r`n"
try {
    Set-Content -Path $Launcher -Value $content -Encoding ASCII
    Write-Host "Created Desktop launcher: $Launcher" -ForegroundColor Green
} catch {
    Write-Host "BLOCKER: could not write Desktop launcher ($($_.Exception.Message))." -ForegroundColor Red
    Write-Host "Fallback: run tools\launch_dashboard.bat directly." -ForegroundColor Yellow
    exit 1
}
