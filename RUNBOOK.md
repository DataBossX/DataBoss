# RUNBOOK — Grocery Report Pipeline

Windows-friendly commands. Run these **on the machine where the documents live**.

## 0. One-time setup
```bat
cd /d D:\DataBoss\DataBossX_Final_Modular       :: or wherever this repo is checked out
py -m pip install -r requirements-grocery.txt
```
The core pipeline runs even with **no** packages installed (it falls back to CSV/Markdown).
`openpyxl` is strongly recommended for the `.xlsx` outputs; `python-docx` for the `.docx`
draft; `pdfplumber`/`PyMuPDF`/`pytesseract`+`Pillow` for PDF/scanned-image text.

## 1. Prove the machinery works (no real data needed)
```bat
py grocery_report_pipeline.py --self-test
```
Generates a **synthetic** corpus and runs every stage. Inspect `output\status_dashboard.html`.

## 2. Run against the real documents  ← the main command
```bat
py grocery_report_pipeline.py --root "D:\DataBoss\DataBossX_Final_Modular"
```
Optional flags:
```bat
:: custom output folder / report name
py grocery_report_pipeline.py --root "D:\DataBoss\DataBossX_Final_Modular" ^
    --output-dir ".\output" --report-name "Grocery_Report"

:: after reviewing quarantine_plan.csv, physically move byte-identical dupes
:: (never deletes; keeps one canonical copy)
py grocery_report_pipeline.py --root "D:\DataBoss\DataBossX_Final_Modular" --apply-quarantine
```

## 3. What to open, in order
1. `output\status_dashboard.html` — RAG status, % per stage, blockers, Monday risk.
2. `output\review_required.csv` — work **red** rows first, then yellow.
3. `output\Grocery_Report_Executive_Summary.md` — the one-page summary.
4. `output\Grocery_Report_DRAFT.docx` / `.md` — the full draft.
5. `output\Grocery_Report_Curative_List.xlsx` — curative / exceptions.
6. `output\conflicts_and_gaps.xlsx` — chain gaps, decimal/acreage conflicts.
7. `output\Grocery_Report_Source_Index.xlsx` — traceability index (file → categories → text).

## 4. Regenerate anytime
The pipeline is **idempotent** — rerun step 2 as documents change; outputs are overwritten
with a fresh timestamp. Originals are never modified.

## 5. Run the tests
```bat
py -m pip install pytest
py -m pytest tests\test_grocery_pipeline.py -v
```

## 6. Troubleshooting
| Symptom | Fix |
| --- | --- |
| `.xlsx` files missing, `.csv` appear instead | `py -m pip install openpyxl` and rerun. |
| `.docx` not produced | `py -m pip install python-docx` and rerun. |
| Many rows `status=no-text` in `source_text_index.csv` | scanned PDFs/images — install `pdfplumber PyMuPDF pytesseract Pillow` + the Tesseract binary, then rerun. |
| `ERROR: root folder does not exist` | fix the `--root` path to the real documents folder. |
| Want to see the plan without writing | run `--self-test` first to preview all outputs. |

## Safety guarantees
- Never deletes or overwrites source files.
- Never invents legal/title/ownership/lease/acreage/decimal/instrument data.
- No network calls, no uploads, no secrets in code or outputs (AI extraction is opt-in and
  reads its key only from the environment).
