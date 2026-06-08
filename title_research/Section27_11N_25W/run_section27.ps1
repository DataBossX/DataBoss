<#
  run_section27.ps1  -  Section 27-11N-25W one-click local finish (Windows).
  Zero manual editing. Prompts for the OKCR API key (hidden), runs a dry-run
  cost estimate, requires explicit approval before any paid download, then
  pulls -> OCRs -> verifies -> rebuilds -> QA -> exports.

  The API key lives ONLY in this process's environment for the duration of the
  run. It is never printed, logged, written to disk, or committed, and is
  wiped in the finally{} block.

  Run:  right-click -> "Run with PowerShell"   (or)   .\run_section27.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot          # project root = this script's folder

function Find-Python {
  foreach ($c in @("py -3","python","python3")) {
    $exe = $c.Split(" ")[0]
    if (Get-Command $exe -ErrorAction SilentlyContinue) { return $c }
  }
  throw "Python not found. Install Python 3 from https://python.org and re-run."
}

try {
  Write-Host "=== Section 27-11N-25W local finish ===" -ForegroundColor Cyan
  $PY = Find-Python
  Write-Host "Using Python: $PY"

  # --- venv + deps (idempotent) ---
  if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (.venv)..."
    & cmd /c "$PY -m venv .venv"
  }
  $venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
  Write-Host "Installing/upgrading Python dependencies..."
  & $venvPy -m pip install --quiet --upgrade pip
  & $venvPy -m pip install --quiet -r requirements.txt

  # --- external tools check (poppler / tesseract) ---
  foreach ($t in @("pdftoppm","tesseract")) {
    if (-not (Get-Command $t -ErrorAction SilentlyContinue)) {
      Write-Warning "$t not on PATH. PDFs will use the PyMuPDF fallback for rendering; tesseract is needed for text OCR. See README_WINDOWS.md."
    }
  }

  # --- hidden API key prompt (session-only) ---
  $secure = Read-Host "Enter OKCountyRecords API key (input hidden)" -AsSecureString
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
  if ([string]::IsNullOrWhiteSpace($plain)) { throw "No API key entered. Aborting." }
  $env:OKCR_API_KEY = $plain
  $plain = $null
  $env:APPROVE_OKCR_DOWNLOADS = "false"      # explicit: not yet approved

  # --- 1) DRY RUN cost estimate (no paid downloads) ---
  Write-Host "`n[1/6] Dry-run cost estimate (no downloads)..." -ForegroundColor Yellow
  & $venvPy scripts\okcr_pull.py --dry-run
  if (Test-Path "records_parsed\download_estimate.json") {
    Write-Host "Estimate written to records_parsed\download_estimate.json"
  }

  # --- explicit approval gate ---
  Write-Host "`nReview the estimate above. Paid downloads will NOT run unless you approve." -ForegroundColor Yellow
  $ans = Read-Host "Type  APPROVE  (all caps) to authorize paid downloads, anything else to stop"
  if ($ans -ne "APPROVE") {
    Write-Host "Not approved. Stopped before any paid download. Nothing was charged." -ForegroundColor Green
    return
  }
  $env:APPROVE_OKCR_DOWNLOADS = "true"        # approved for THIS pass only

  # --- 2) pull Priority-1 instruments ---
  Write-Host "`n[2/6] Downloading Priority-1 instruments..." -ForegroundColor Yellow
  & $venvPy scripts\okcr_pull.py

  # --- 3) OCR ---
  Write-Host "`n[3/6] OCR of downloaded documents..." -ForegroundColor Yellow
  & $venvPy scripts\okcr_ocr.py

  # --- 4) verify chain ---
  Write-Host "`n[4/6] Verifying 2017-2026 assignment chain..." -ForegroundColor Yellow
  & $venvPy scripts\verify_chain.py

  # --- 5) rebuild workbook + QA ---
  Write-Host "`n[5/6] Rebuilding final workbook + QA..." -ForegroundColor Yellow
  & $venvPy scripts\build_final.py
  & $venvPy scripts\qa_workbook.py

  # --- 6) refresh logs + export ---
  Write-Host "`n[6/6] Updating logs & exporting deliverables..." -ForegroundColor Yellow
  & $venvPy scripts\finalize_logs.py

  Write-Host "`n=== DONE ===" -ForegroundColor Green
  Write-Host "Final workbook : deliverables\11N_25W_27_Beckham_Co_Diversified_Cursory_Report_FULLY_UPDATED.xlsx"
  Write-Host "Chain result   : records_parsed\chain_verification.json"
  Write-Host "OCR text       : records_ocr\*.txt"
  Write-Host "NOTE: NRI/WI stay UNRESOLVED/ESTIMATE-ONLY unless the chain fully verified AND NMA/ORRI are resolved."
}
finally {
  # wipe credentials from this process no matter what happened
  Remove-Item Env:OKCR_API_KEY -ErrorAction SilentlyContinue
  Remove-Item Env:APPROVE_OKCR_DOWNLOADS -ErrorAction SilentlyContinue
  if ($plain) { $plain = $null }
  Write-Host "`n(API key cleared from environment.)" -ForegroundColor DarkGray
}
