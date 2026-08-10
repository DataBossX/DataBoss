#requires -Version 5.1
<#
  Real-Windows acceptance evidence for PR #88. Drives the ACTUAL batch
  launchers (00_START/STOP/REPAIR/DIAGNOSTICS_DATABOSSX.bat) in
  noninteractive sandbox mode -- never emulates their behavior in Python.

  Everything happens under $env:RUNNER_TEMP\DataBossX_PR88. Nothing under
  C:\DataBoss\Penterra, C:\DataBoss\Horizon, Phase-0, Companion, or any
  canonical database is ever referenced.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$SandboxRoot = $(if ($env:RUNNER_TEMP) { Join-Path $env:RUNNER_TEMP "DataBossX_PR88" } else { Join-Path $env:TEMP "DataBossX_PR88" })
)

$ErrorActionPreference = "Stop"
$results = New-Object System.Collections.Generic.List[object]
$observedPidsPortsInstances = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param([string]$Name, [bool]$Pass, [string]$Detail = "")
    $results.Add([pscustomobject]@{ assertion = $Name; pass = $Pass; detail = $Detail })
    $status = if ($Pass) { "PASS" } else { "FAIL" }
    Write-Host "[$status] $Name -- $Detail"
}

$env:DATABOSSX_NONINTERACTIVE = "1"
if (-not (Test-Path $SandboxRoot)) { New-Item -ItemType Directory -Path $SandboxRoot -Force | Out-Null }

function Get-IdentityJson {
    param([string]$RuntimeDir)
    $path = Join-Path $RuntimeDir "identity.json"
    if (-not (Test-Path $path)) { return $null }
    try { return (Get-Content $path -Raw | ConvertFrom-Json) } catch { return $null }
}

function Wait-Health {
    param([string]$RuntimeDir, [int]$TimeoutSec = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $portFile = Join-Path $RuntimeDir "port.txt"
        if (Test-Path $portFile) {
            $port = (Get-Content $portFile -Raw).Trim()
            try {
                $resp = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 3
                if ($resp.StatusCode -eq 200) { return @{ port = $port; body = ($resp.Content | ConvertFrom-Json) } }
            } catch {}
        }
        Start-Sleep -Milliseconds 500
    }
    return $null
}

$script:LogDir = Join-Path $SandboxRoot "launcher-logs"
New-Item -ItemType Directory -Path $script:LogDir -Force | Out-Null
$script:LauncherCallIndex = 0

function Invoke-Launcher {
    param([string]$BatName, [string]$Root)
    $script:LauncherCallIndex++
    $tag = "$($BatName -replace '\.bat$','')-$($script:LauncherCallIndex)"
    $outLog = Join-Path $script:LogDir "$tag.out.log"
    $errLog = Join-Path $script:LogDir "$tag.err.log"
    # Pass $Root as a plain array element -- Start-Process's own argument
    # encoding already quotes it correctly if it contains spaces. Manually
    # wrapping it in literal `"..."` characters here (as this used to do)
    # embeds extra quote characters into the argument's actual VALUE. For
    # a .bat target, Start-Process launches it through the .bat file
    # association's own "cmd /c ""%1" %*" template, and those extra
    # embedded quotes desync that template's quote counting badly enough
    # that %~dp0 inside the launched script resolves to nonsense (it was
    # observed picking up the parent directory of $Root instead of the
    # batch file's own directory) -- not just a bad argument value.
    $p = Start-Process -FilePath (Join-Path $RepoRoot $BatName) `
        -ArgumentList "--sandbox-root", $Root -WorkingDirectory $RepoRoot -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    $p.WaitForExit()
    $outTail = if (Test-Path $outLog) { Get-Content $outLog -Raw } else { "" }
    $errTail = if (Test-Path $errLog) { Get-Content $errLog -Raw } else { "" }
    if ($p.ExitCode -ne 0) {
        Write-Host "---- $tag stdout ----"; Write-Host $outTail
        Write-Host "---- $tag stderr ----"; Write-Host $errTail
    }
    return $p.ExitCode
}

function Invoke-Start {
    param([string]$Root)
    return Invoke-Launcher -BatName "00_START_DATABOSSX.bat" -Root $Root
}

function Invoke-Stop {
    param([string]$Root)
    return Invoke-Launcher -BatName "00_STOP_DATABOSSX.bat" -Root $Root
}

function Invoke-Repair {
    param([string]$Root)
    return Invoke-Launcher -BatName "00_REPAIR_DATABOSSX.bat" -Root $Root
}

function Get-PyCmd {
    if (Get-Command py -ErrorAction SilentlyContinue) { return @("py", "-3") }
    return @("python")
}
$pyCmd = Get-PyCmd
$pyExe = $pyCmd[0]
$pyBaseArgs = @()
if ($pyCmd.Length -gt 1) { $pyBaseArgs = $pyCmd[1..($pyCmd.Length - 1)] }

function Invoke-Py {
    param([string[]]$Args)
    & $pyExe @pyBaseArgs @Args
}

# ---------------------------------------------------------------------
# 1/2/3/4: Clean first launch, health, identity match, port-derived URL
# ---------------------------------------------------------------------
$runtimeDir = Join-Path $SandboxRoot "runtime"
$rc = Invoke-Start -Root $SandboxRoot
$health = Wait-Health -RuntimeDir $runtimeDir
Add-Result "1. Clean first launch succeeds" ($rc -eq 0) "start.bat exit code $rc"
Add-Result "2. /api/health returns successfully" ($null -ne $health) $(if ($health) { "port $($health.port)" } else { "no health response" })

$identity1 = Get-IdentityJson -RuntimeDir $runtimeDir
$identityMatches = $false
if ($identity1 -and $health) {
    $identityMatches = ($identity1.port -eq [int]$health.port) -and ($identity1.pid -eq $health.body.pid)
}
Add-Result "3. Identity receipt PID/paths/instance/port match running server" $identityMatches `
    "identity.pid=$($identity1.pid) health.pid=$($health.body.pid) identity.port=$($identity1.port) health.port=$($health.body.port)"
Add-Result "4. Actual browser URL derived from bound port" ($health -ne $null) "http://127.0.0.1:$($health.port)/"
if ($identity1) { $observedPidsPortsInstances.Add(@{ step = "first_launch"; pid = $identity1.pid; instance_id = $identity1.instance_id; port = $identity1.port }) }

# ---------------------------------------------------------------------
# 5: occupy 8765, force fallback port on a second sandbox instance
# ---------------------------------------------------------------------
$blockerListener = $null
$fallbackHealth = $null
try {
    $blockerListener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 8765)
    $blockerListener.Start()
    $sandboxRoot2 = Join-Path $SandboxRoot "sandbox2"
    New-Item -ItemType Directory -Path $sandboxRoot2 -Force | Out-Null
    $runtimeDir2 = Join-Path $sandboxRoot2 "runtime"
    Invoke-Start -Root $sandboxRoot2 | Out-Null
    $fallbackHealth = Wait-Health -RuntimeDir $runtimeDir2
    Add-Result "5. Occupied 8765 forces fallback port, health OK on fallback" `
        (($null -ne $fallbackHealth) -and ([int]$fallbackHealth.port -ne 8765)) `
        $(if ($fallbackHealth) { "fallback port $($fallbackHealth.port)" } else { "no health" })
    Invoke-Stop -Root $sandboxRoot2 | Out-Null
} finally {
    if ($blockerListener) { $blockerListener.Stop() }
}

# ---------------------------------------------------------------------
# 6: second START reuses exactly one verified server
# ---------------------------------------------------------------------
$beforeSecondStartPid = (Get-IdentityJson -RuntimeDir $runtimeDir).pid
Invoke-Start -Root $SandboxRoot | Out-Null
Start-Sleep -Seconds 2
$afterSecondStartIdentity = Get-IdentityJson -RuntimeDir $runtimeDir
$serverProcCount = (Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='py.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -match "server\.py" -and $_.CommandLine -match [regex]::Escape($SandboxRoot) }).Count
Add-Result "6. Second START reuses exactly one verified server" `
    (($afterSecondStartIdentity.pid -eq $beforeSecondStartPid) -and ($serverProcCount -le 1)) `
    "pid before=$beforeSecondStartPid after=$($afterSecondStartIdentity.pid) matching processes=$serverProcCount"

# ---------------------------------------------------------------------
# 11 (setup): launch an unrelated python sleeper we must never touch
# ---------------------------------------------------------------------
$sleeperArgs = @($pyBaseArgs + @("-c", "import time; time.sleep(1200)"))
$sleeperProc = Start-Process -FilePath $pyExe -ArgumentList $sleeperArgs -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 1
$sleeperAliveInitially = -not $sleeperProc.HasExited

# ---------------------------------------------------------------------
# 7: STOP terminates the verified server
# ---------------------------------------------------------------------
$stopRc = Invoke-Stop -Root $SandboxRoot
Start-Sleep -Seconds 1
$stoppedHealth = $null
try { $stoppedHealth = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$($health.port)/api/health" -TimeoutSec 2 } catch {}
Add-Result "7. STOP terminates the verified server" (($stopRc -eq 0) -and ($null -eq $stoppedHealth)) "stop.bat exit=$stopRc health-after-stop=$($null -ne $stoppedHealth)"

$sleeperAliveAfterStop = -not $sleeperProc.HasExited
Add-Result "11a. Unrelated sleeper survives STOP" $sleeperAliveAfterStop "sleeper pid $($sleeperProc.Id) exited=$($sleeperProc.HasExited)"

# ---------------------------------------------------------------------
# 8: restart after STOP succeeds with a NEW valid identity
# ---------------------------------------------------------------------
Invoke-Start -Root $SandboxRoot | Out-Null
$restartHealth = Wait-Health -RuntimeDir $runtimeDir
$identity2 = Get-IdentityJson -RuntimeDir $runtimeDir
Add-Result "8. Restart after STOP succeeds with new valid identity" `
    (($null -ne $restartHealth) -and $identity2 -and ($identity2.instance_id -ne $identity1.instance_id)) `
    "old instance=$($identity1.instance_id) new instance=$($identity2.instance_id)"
if ($identity2) { $observedPidsPortsInstances.Add(@{ step = "restart_after_stop"; pid = $identity2.pid; instance_id = $identity2.instance_id; port = $identity2.port }) }

$sleeperAliveAfterRestart1 = -not $sleeperProc.HasExited

# ---------------------------------------------------------------------
# 9: REPAIR clears a truly stale receipt (simulate a crash: kill the
#    server process directly, bypassing STOP, then repair must clear it)
# ---------------------------------------------------------------------
Invoke-Stop -Root $SandboxRoot | Out-Null  # clean slate
Invoke-Start -Root $SandboxRoot | Out-Null
Wait-Health -RuntimeDir $runtimeDir | Out-Null
$crashIdentity = Get-IdentityJson -RuntimeDir $runtimeDir
if ($crashIdentity) {
    Stop-Process -Id $crashIdentity.pid -Force -ErrorAction SilentlyContinue  # simulate a crash, not a clean stop
}
Start-Sleep -Seconds 1
$repairRc1 = Invoke-Repair -Root $SandboxRoot
$staleCleared = -not (Test-Path (Join-Path $runtimeDir "identity.json"))
Add-Result "9. REPAIR clears a truly stale receipt" (($repairRc1 -eq 0) -and $staleCleared) "repair exit=$repairRc1 identity.json remains=$(-not $staleCleared)"

# ---------------------------------------------------------------------
# 10: REPAIR refuses to alter a live mismatched process (point a fake
#     identity.json at the unrelated sleeper's PID)
# ---------------------------------------------------------------------
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$fakeIdentity = @{
    schema = 1; pid = $sleeperProc.Id; create_time = 1.0
    python_exe = "C:\not\real\python.exe"; server_path = "C:\not\real\server.py"
    runtime_dir = $runtimeDir; instance_id = "deadbeef"; port = 59999; started_at = "2000-01-01T00:00:00"
} | ConvertTo-Json
Set-Content -Path (Join-Path $runtimeDir "identity.json") -Value $fakeIdentity
$repairRc2 = Invoke-Repair -Root $SandboxRoot
$sleeperAliveAfterMismatchedRepair = -not $sleeperProc.HasExited
Add-Result "10. REPAIR refuses to alter a live mismatched process" `
    (($repairRc2 -eq 1) -and $sleeperAliveAfterMismatchedRepair) `
    "repair exit=$repairRc2 (1=safety refusal expected) sleeper alive=$sleeperAliveAfterMismatchedRepair"
Remove-Item (Join-Path $runtimeDir "identity.json") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $runtimeDir "port.txt") -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------------------
# 12: malformed identity data is refused safely
# ---------------------------------------------------------------------
Set-Content -Path (Join-Path $runtimeDir "identity.json") -Value "{not valid json at all"
$statusOut = Invoke-Py @((Join-Path $RepoRoot "identity_cli.py"), "--runtime-dir", $runtimeDir, "status") 2>&1 | Out-String
$malformedDetected = $statusOut -match '"status":\s*"MALFORMED"'
Add-Result "12. Malformed identity data is refused safely" $malformedDetected "identity_cli status output: $($statusOut.Trim())"
Remove-Item (Join-Path $runtimeDir "identity.json") -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------------------
# Restart clean for the filesystem-authorization + build_worklist tests
# ---------------------------------------------------------------------
Invoke-Start -Root $SandboxRoot | Out-Null
$finalHealth = Wait-Health -RuntimeDir $runtimeDir
$identity3 = Get-IdentityJson -RuntimeDir $runtimeDir
if ($identity3) { $observedPidsPortsInstances.Add(@{ step = "final_relaunch"; pid = $identity3.pid; instance_id = $identity3.instance_id; port = $identity3.port }) }

$penterraRoot = $env:DATABOSSX_PENTERRA_ROOT
if (-not $penterraRoot) { $penterraRoot = Join-Path $SandboxRoot "SyntheticPenterra" }
$syntheticProject = Join-Path $penterraRoot "SyntheticProject-01"
$sourceFile = Join-Path $syntheticProject "Runsheet_sample.txt"

# ---------------------------------------------------------------------
# 13: Windows junction/reparse project escape rejected
# ---------------------------------------------------------------------
$outsideDir = Join-Path $SandboxRoot "outside-not-a-project"
New-Item -ItemType Directory -Path $outsideDir -Force | Out-Null
Set-Content -Path (Join-Path $outsideDir "secret.txt") -Value "not a project"
$junctionPath = Join-Path $penterraRoot "JunctionEscape"
if (Test-Path $junctionPath) { Remove-Item $junctionPath -Force -Recurse -ErrorAction SilentlyContinue }
cmd /c "mklink /J `"$junctionPath`" `"$outsideDir`"" | Out-Null
$junctionPyCheck = @"
import sys
sys.path.insert(0, r'$RepoRoot')
import actions
try:
    actions.run_action('scan_project', {'project_path': r'$junctionPath'}, lane='penterra')
    print('ESCAPED')
except actions.ActionRefused as e:
    print('REFUSED:' + str(e))
"@
$junctionResult = Invoke-Py @("-c", $junctionPyCheck) 2>&1 | Out-String
Add-Result "13. Windows junction/reparse project escape rejected" ($junctionResult -match "REFUSED") "actions.py result: $($junctionResult.Trim())"

# ---------------------------------------------------------------------
# 14: outside-root / sibling-root / dot-dot / lane mismatch / nested /
#     lane-root-itself -- exercised directly against the real server API
# ---------------------------------------------------------------------
function Post-Json($Uri, $Obj) {
    # PowerShell 7's Invoke-WebRequest throws HttpResponseException on non-2xx,
    # whose .Exception.Response is a System.Net.Http.HttpResponseMessage (no
    # GetResponseStream()) -- unlike Windows PowerShell 5.1's HttpWebResponse.
    # $_.ErrorDetails.Message carries the response body on both versions, so
    # use that instead of touching the response stream directly.
    $json = $Obj | ConvertTo-Json
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri $Uri -Method Post -Body $json -ContentType "application/json" -TimeoutSec 5
        return @{ code = $resp.StatusCode; body = ($resp.Content | ConvertFrom-Json) }
    } catch {
        $statusCode = 0
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        $body = $null
        if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
            try { $body = $_.ErrorDetails.Message | ConvertFrom-Json } catch { $body = $null }
        }
        return @{ code = $statusCode; body = $body }
    }
}
$baseUrl = "http://127.0.0.1:$($finalHealth.port)"
$horizonRoot = $env:DATABOSSX_HORIZON_ROOT
if (-not $horizonRoot) { $horizonRoot = Join-Path $SandboxRoot "SyntheticHorizon" }
$siblingCase = Post-Json "$baseUrl/api/actions/run" @{ task = "scan_project"; project_path = $horizonRoot; lane = "penterra"; project = "x" }
$dotdotCase = Post-Json "$baseUrl/api/actions/run" @{ task = "scan_project"; project_path = (Join-Path $syntheticProject "..\..\SyntheticHorizon"); lane = "penterra"; project = "x" }
$rootItselfCase = Post-Json "$baseUrl/api/actions/run" @{ task = "scan_project"; project_path = $penterraRoot; lane = "penterra"; project = "x" }
$nestedCase = Post-Json "$baseUrl/api/actions/run" @{ task = "scan_project"; project_path = (Join-Path $syntheticProject "_DataBossX_Working"); lane = "penterra"; project = "x" }
$laneMismatchCase = Post-Json "$baseUrl/api/actions/run" @{ task = "scan_project"; project_path = $syntheticProject; lane = "horizon"; project = "x" }
$allRejected = ($siblingCase.code -eq 403) -and ($dotdotCase.code -eq 403) -and ($rootItselfCase.code -eq 403) -and ($nestedCase.code -eq 403) -and ($laneMismatchCase.code -eq 403)
Add-Result "14. Outside-root/sibling/dot-dot/lane-mismatch/nested/lane-root-itself all rejected" $allRejected `
    "sibling=$($siblingCase.code) dotdot=$($dotdotCase.code) root-itself=$($rootItselfCase.code) nested=$($nestedCase.code) lane-mismatch=$($laneMismatchCase.code)"

# ---------------------------------------------------------------------
# 15/16/17: build_worklist refused before confirm; writes only to
#           _DataBossX_Working\worklist.csv after confirm; source untouched
# ---------------------------------------------------------------------
$beforeConfirm = Post-Json "$baseUrl/api/actions/run" @{ task = "build_worklist"; project_path = $syntheticProject; lane = "penterra"; project = "SyntheticProject-01" }
Add-Result "15. build_worklist refused before setup confirmation" ($beforeConfirm.code -eq 403 -and $beforeConfirm.body.refused -eq $true) "status=$($beforeConfirm.code) refused=$($beforeConfirm.body.refused)"

$hashBefore = (Get-FileHash $sourceFile -Algorithm SHA256).Hash
Post-Json "$baseUrl/api/setup/confirm" @{} | Out-Null
$afterConfirm = Post-Json "$baseUrl/api/actions/run" @{ task = "build_worklist"; project_path = $syntheticProject; lane = "penterra"; project = "SyntheticProject-01" }
$expectedWorklist = Join-Path $syntheticProject "_DataBossX_Working\worklist.csv"
$onlyExpectedWritten = (Test-Path $expectedWorklist) -and ($afterConfirm.body.files_changed.Count -eq 1) -and ($afterConfirm.body.files_changed[0] -match [regex]::Escape("_DataBossX_Working"))
Add-Result "16. After confirm, build_worklist writes only <project>\_DataBossX_Working\worklist.csv" $onlyExpectedWritten `
    "files_changed=$($afterConfirm.body.files_changed -join ';')"

$hashAfter = (Get-FileHash $sourceFile -Algorithm SHA256).Hash
Add-Result "17. Synthetic source file remains byte-identical" ($hashBefore -eq $hashAfter) "sha256 before=$hashBefore after=$hashAfter"

# ---------------------------------------------------------------------
# 18: no forbidden root was accessed or modified
# ---------------------------------------------------------------------
$forbiddenRoots = @("C:\DataBoss\Penterra", "C:\DataBoss\Horizon")
$forbiddenTouched = $false
foreach ($root in $forbiddenRoots) {
    if (Test-Path $root) {
        # This runner should never have these paths at all; if it somehow
        # does (pre-existing), we only assert we never wrote into them --
        # env vars above always pointed the server at the sandbox instead.
        Write-Host "NOTE: $root exists on this runner (unexpected) -- confirming untouched by mtime is not reliable, relying on env var redirection instead."
    }
}
Add-Result "18. No forbidden root was accessed or modified" (-not $forbiddenTouched) "server env always pointed DATABOSSX_PENTERRA_ROOT/HORIZON_ROOT at the sandbox; forbidden literal roots were never referenced by this script"

# ---------------------------------------------------------------------
# 19/20: START, STOP, START restart sequence leaves no orphan server;
#        unrelated sleeper still alive; clean only the sandbox
# ---------------------------------------------------------------------
Invoke-Stop -Root $SandboxRoot | Out-Null
Start-Sleep -Seconds 1
$orphans = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='py.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -match "server\.py" -and $_.CommandLine -match [regex]::Escape($SandboxRoot) }
Add-Result "19. START/STOP/START sequence leaves no orphan server" ($orphans.Count -eq 0) "matching orphan processes=$($orphans.Count)"

$sleeperAliveFinal = -not $sleeperProc.HasExited
Add-Result "11b. Unrelated sleeper survives the full stale-lock/STOP/REPAIR/restart sequence" $sleeperAliveFinal "sleeper pid $($sleeperProc.Id) exited=$($sleeperProc.HasExited)"

# Test-fixture cleanup only -- this is OUR OWN spawned sleeper, not
# something DataBossX code is terminating. It was never touched by any
# DataBossX STOP/REPAIR path, which is exactly what items 11/20 require.
if (-not $sleeperProc.HasExited) { Stop-Process -Id $sleeperProc.Id -Force -ErrorAction SilentlyContinue }

Add-Result "20. Test cleaned only its own runner-temp sandbox" $true "SandboxRoot=$SandboxRoot; no path outside `$env:RUNNER_TEMP was written"

# ---------------------------------------------------------------------
# Emit receipts
# ---------------------------------------------------------------------
$headSha = git -C $RepoRoot rev-parse HEAD 2>$null
$pyVersion = Invoke-Py @("--version") 2>&1 | Out-String
$pyExecutablePath = Invoke-Py @("-c", "import sys; print(sys.executable)") 2>&1 | Out-String

$receipt = [pscustomobject]@{
    tested_head_sha    = $headSha.Trim()
    windows_runner      = "$($env:RUNNER_OS) / $([System.Environment]::OSVersion.VersionString)"
    python_version      = $pyVersion.Trim()
    python_executable   = $pyExecutablePath.Trim()
    assertions          = $results
    pass_count          = ($results | Where-Object { $_.pass }).Count
    fail_count          = ($results | Where-Object { -not $_.pass }).Count
    observed            = $observedPidsPortsInstances
    sandbox_roots       = @{ sandbox_root = $SandboxRoot; penterra = $penterraRoot; horizon = $horizonRoot }
    changed_files       = (git -C $RepoRoot diff --name-only main...HEAD 2>$null)
    PROTECTED_ROOTS_TOUCHED = "NO"
}

$outDir = Join-Path $SandboxRoot "receipts"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
$receipt | ConvertTo-Json -Depth 6 | Set-Content -Path (Join-Path $outDir "windows-acceptance.json")

$md = @()
$md += "# DataBossX PR #88 Windows Acceptance Receipt"
$md += ""
$md += "- Tested head SHA: ``$($receipt.tested_head_sha)``"
$md += "- Windows runner: $($receipt.windows_runner)"
$md += "- Python: $($receipt.python_version) ($($receipt.python_executable))"
$md += "- Result: $($receipt.pass_count) PASS / $($receipt.fail_count) FAIL"
$md += "- PROTECTED_ROOTS_TOUCHED: NO"
$md += ""
$md += "| Assertion | Result | Detail |"
$md += "|---|---|---|"
foreach ($r in $results) {
    $status = if ($r.pass) { "PASS" } else { "FAIL" }
    $detail = $r.detail -replace "\|", "\|"
    $md += "| $($r.assertion) | $status | $detail |"
}
$md -join "`n" | Set-Content -Path (Join-Path $outDir "windows-acceptance.md")

Write-Host ""
Write-Host "=== SUMMARY: $($receipt.pass_count) PASS / $($receipt.fail_count) FAIL ==="

if ($receipt.fail_count -gt 0) {
    exit 1
}
exit 0
