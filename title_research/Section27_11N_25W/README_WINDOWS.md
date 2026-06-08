# Section 27-11N-25W - One-Click Local Finish (Windows)

This folder is a self-contained project. On a machine that can reach
**okcountyrecords.com**, it pulls the 8 Priority-1 assignment instruments,
OCRs them, verifies the 2017-2026 corporate chain, rebuilds the final
workbook, runs QA, and exports everything - with no manual editing and no
keys ever pasted into code.

## 1. One-time prerequisites
1. **Python 3** - https://www.python.org/downloads/ (check "Add python.exe to PATH").
2. **Tesseract OCR** (for text extraction) - UB-Mannheim build:
   https://github.com/UB-Mannheim/tesseract/wiki  -> add its folder to PATH.
3. **Poppler** (PDF rendering; optional - PyMuPDF is used as a fallback):
   https://github.com/oschwartz10612/poppler-windows/releases -> add `bin` to PATH.

(Everything else - openpyxl, requests, pillow, pymupdf, etc. - is installed
automatically into a local `.venv` the first time you run.)

## 2. Run it
Double-click **`run_section27.bat`**
  (or right-click `run_section27.ps1` -> "Run with PowerShell").

You will be asked to:
1. **Enter your OKCR API key** - input is hidden; it stays in memory only and
   is wiped when the run ends. It is never printed, logged, written, or committed.
2. **Review the dry-run cost estimate** (page/instrument counts; no charge yet).
3. **Type `APPROVE`** to authorize paid downloads. Anything else stops with $0 spent.

The runner then does, automatically:
`pull -> OCR -> verify chain -> rebuild workbook -> QA -> update logs -> export`.

## 3. Where the outputs land
| Output | Path |
|---|---|
| **Final workbook** | `deliverables\11N_25W_27_..._FULLY_UPDATED.xlsx` |
| Chain verification result | `records_parsed\chain_verification.json` |
| OCR text per instrument | `records_ocr\*.txt` |
| Raw downloaded PDFs | `records_raw\*.pdf` |
| Cost estimate | `records_parsed\download_estimate.json` |
| Download manifest | `records_parsed\download_manifest_actual.csv` |
| API/OCR log | `deliverables\SECTION_27_API_AND_OCR_LOG.md` |
| Approval manifest | `deliverables\NEEDS_APPROVAL_TO_DOWNLOAD_RECORDS.md` |

QA Audit and Change Log are tabs **inside** the workbook and update automatically.

## 4. Confidence rule (important)
- The chain **verifies** only when the core succession instruments
  (2266/194, 2307/894, 2308/123, 2340/218, 2451/4) are OCR-confirmed.
- Even when verified, **NRI/WI decimals stay UNRESOLVED / ESTIMATE-ONLY.**
  Chain verification proves *ownership succession*, not the WI decimal - that
  still needs per-lessor net mineral acres and ORRI netting (Gap #1/#7/#8).
- If OCR is poor (handwritten/low-quality scans), `chain_verification.json`
  will show `chain_verified: false`; the report then keeps everything at the
  current (unverified) confidence. Inspect `records_ocr\*.txt` and re-run.

## 5. Re-running
Safe to re-run; downloads are idempotent (cached files are skipped). To force a
fresh pull, delete `records_raw\*.pdf` first.

## 6. If anything has to come back to Claude for re-ingest
Send back (these contain **no secrets**):
- `records_parsed\chain_verification.json`
- `records_parsed\download_manifest_actual.csv`
- `records_ocr\*.txt`  (zip the folder)
- `deliverables\...FULLY_UPDATED.xlsx`
Do **not** send your `.env`, API key, or anything containing the key.
