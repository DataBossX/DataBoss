# Grocery Report — RUNBOOK (for Rodney)

Windows-friendly. Copy/paste commands. The pipeline **never deletes or edits your
source files** and writes everything under `<project>\output\`.

## 0. One-time setup
```bat
:: from the repo folder
python --version
:: unlock full coverage (Excel out, PDF/DOCX text, OCR). Optional but recommended:
pip install -r report_pipeline\requirements.txt
```
For **scanned PDFs / images**, also install the Tesseract OCR engine (Windows
build): https://github.com/UB-Mannheim/tesseract/wiki — then reopen your terminal.

> The pipeline still runs WITHOUT these installs. **`.xlsx` outputs are always
> produced** (a built-in stdlib Excel writer is used when openpyxl is absent).
> Only PDF/DOCX/OCR text extraction needs the optional libs; skipped items are
> listed in `output\source_text_index.csv`.

## 1. Run the whole pipeline
Easiest — double-click **`RUN_REPORT_PIPELINE.bat`** (edit `PROJECT_ROOT` inside it
first if your documents live elsewhere), or:
```bat
python run_report_pipeline.py --root "D:\DataBoss\DataBossX_Final_Modular"
```
Outputs land in `D:\DataBoss\DataBossX_Final_Modular\output\`.

## 2. What to open first
```
output\status_dashboard.html            <- start here (green/yellow/red)
output\Grocery_Report_Executive_Summary.md
output\review_required.csv              <- your worklist (high-severity)
output\duplicate_candidates.csv         <- dupes (nothing moved yet)
output\Grocery_Report_DRAFT.md
```

## 3. Handle duplicates (no auto-delete, reversible)
1. Open `output\quarantine_plan.csv`. Each row is a **candidate** with a proposed
   destination and `duplicate_of`.
2. Add a column **`approved`** and put `YES` on the rows you agree to quarantine.
3. Dry-run (moves nothing, just shows what would happen):
   ```bat
   python -m report_pipeline.quarantine_exec --root "D:\DataBoss\DataBossX_Final_Modular"
   ```
4. Apply (moves ONLY approved rows into `quarantine\duplicates\`, verifies each
   file's hash is unchanged, and writes a reversible `quarantine_manifest.csv`):
   ```bat
   python -m report_pipeline.quarantine_exec --root "D:\DataBoss\DataBossX_Final_Modular" --apply
   ```
   Nothing is ever deleted; unapproved and protected files are refused.
5. **Rerun the pipeline (step 1)** so decimal sums aren't inflated by duplicates.

## 3b. Traceability gate (no-fabrication check)
The full run does this automatically, but you can run it on its own; it exits
non-zero if any fact lacks a source or a high-value field is low-confidence and
unflagged:
```bat
python -m report_pipeline.verify --root "D:\DataBoss\DataBossX_Final_Modular"
```
Output: `output\traceability_report.csv`.

## 3c. Optional AI enrichment (audited)
Fills only BLANK party/date/citation fields, never numeric interest math, and
writes `output\ai_extraction_audit.csv`. No-op unless an LLM key is set:
```bat
python run_report_pipeline.py --root "D:\..." --ai
```

## 4. Rerun a single stage (advanced)
The stages read the CSVs in `output\`, so rerunning the whole thing is cheap and
safe. Just run the command in step 1 again — it overwrites only its own outputs.

## 5. Verify it's working
```bat
python -m unittest tests.test_report_pipeline -v
```
Expect `OK`. This runs the pipeline against a built-in synthetic deed/assignment/
lease/duplicate fixture.

## Existing assets you already have
- `doto_image_commander\` in this repo has a PDF processor + OCR analyzer + audit
  DB (Streamlit app). If your PDFs are tricky, that stack can pre-OCR into text
  files that this pipeline will then ingest from `output\extracted_text\`.

## Troubleshooting
| Symptom | Fix |
|--------|-----|
| `needs_dependency` in source_text_index | `pip install -r report_pipeline\requirements.txt` |
| `needs_ocr` rows | install Tesseract binary; rerun |
| `.xlsx` outputs missing | install `openpyxl`; CSVs are always written |
| `.docx` not generated | install `python-docx`; a `.SKIPPED.txt` note is left |
| Everything is "unknown/review" | check that `--root` points at the real documents |
