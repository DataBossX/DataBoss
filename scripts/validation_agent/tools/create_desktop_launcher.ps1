<#
    Creates a Desktop launcher for the DataBossX Validation Agent.
    Produces:
      - "<Desktop>\DataBossX Validation Agent.bat"  (always)
      - "<Desktop>\DataBossX Validation Agent.lnk"  (best effort .lnk shortcut)
    The .bat is the only file placed outside the module folder, by design.
#>
$ErrorActionPreference = "Stop"
$AgentRoot = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath("Desktop")
$LauncherBat = Join-Path $Desktop "DataBossX Validation Agent.bat"
$Target = Join-Path $AgentRoot "tools\launch_dashboard.bat"

$content = @"
@echo off
REM Desktop launcher for the DataBossX Validation Agent
call "$Target"
"@
Set-Content -Path $LauncherBat -Value $content -Encoding ASCII
Write-Host "Created: $LauncherBat" -ForegroundColor Green

try {
    $WScript = New-Object -ComObject WScript.Shell
    $LnkPath = Join-Path $Desktop "DataBossX Validation Agent.lnk"
    $Shortcut = $WScript.CreateShortcut($LnkPath)
    $Shortcut.TargetPath = $Target
    $Shortcut.WorkingDirectory = $AgentRoot
    $Shortcut.Description = "Launch the DataBossX Validation Agent dashboard"
    $Shortcut.Save()
    Write-Host "Created: $LnkPath" -ForegroundColor Green
} catch {
    Write-Host "Note: .lnk shortcut could not be created ($_). The .bat launcher works." -ForegroundColor Yellow
}
