# Grocery Report — Pipeline Plan

A deterministic-first, audited, rerunnable pipeline. Each stage reads the prior
stage's CSV and writes its own, so any stage can be rerun independently. No
fabrication: fields are emitted only when found; otherwise blank + REVIEW REQUIRED.

## Data flow
```
PROJECT_ROOT (source docs, read-only)
   │
   ▼
A. Inventory ───────────► output/file_inventory.csv/.xlsx
B. Dedupe ──────────────► duplicate_candidates.csv, quarantine_plan.csv   (NO DELETE)
C. Text extract ────────► extracted_text/*.txt, source_text_index.csv
D. Classify ────────────► document_classification.csv
E. Structured facts ────► extracted_facts.csv/.xlsx        (source-linked, confidence)
F. Reconcile ───────────► reconciliation_table / chain_summary / conflicts_and_gaps
G. Validate ────────────► validation_report.xlsx, review_required.csv
H. Assemble ────────────► Grocery_Report_DRAFT.md/.docx, Executive_Summary,
                          Curative_List, Source_Index
I. Dashboard ───────────► status_dashboard.html/.csv
```

## Stage detail
- **A. Inventory** — recursive scan (skips .git/node_modules/output/etc.); records
  path, relpath, ext, size, mtime, **sha256**, likely type, status, timestamp.
- **B. Dedupe** — exact via sha256 (deterministic keeper = lexicographically first
  path); fuzzy via normalized filename stem (strips copy/final/v2/(1)); optional
  rapidfuzz. Emits a **quarantine plan** with proposed dest under `quarantine/`;
  **never moves or deletes** — that is a human-approved step.
- **C. Text extract** — txt/csv/md read directly; PDF via pypdf/pdfminer; DOCX via
  python-docx; XLSX via openpyxl; images via Tesseract OCR. Missing lib →
  `needs_dependency`; scanned PDF with no text → `needs_ocr`. Each row carries a
  method + confidence.
- **D. Classify** — 15 categories by keyword hits in filename (weighted) + text;
  confidence from hit count; unknown/low → REVIEW REQUIRED.
- **E. Structured facts** — label-based (`Grantor:`…) plus deterministic patterns
  for instrument no., book/page, ISO/US dates, acreage, decimal interest,
  royalty fractions, and Sec-Twp-Rng legal descriptions. Per-row confidence;
  high-value low-confidence and missing-citation flags. **Every row records its
  source file** (+ page/sheet hook).
- **F. Reconcile** — normalize parties & tracts; order each tract's instruments by
  best available date (recording > effective > execution); build from→to chains;
  flag **chain gaps** (prior grantee ≠ next grantor); sum **decimal interests**
  per tract and flag deviation >0.0005 from 1.0.
- **G. Validate** — missing recording data, missing citations, impossible dates,
  duplicate instruments, decimal-sum mismatches, facts-without-classification,
  high-value low-confidence, chain gaps. High-severity → `review_required.csv`.
- **H. Assemble** — executive summary, draft report (MD always; DOCX when
  python-docx present), curative/exceptions list, and a source index (every file
  + hash + type). Lease/OGL and reconciliation tables inline.
- **I. Dashboard** — per-stage % complete, KPIs, blockers, and a green/yellow/red
  Monday posture in a self-contained HTML file (no external assets).

## Design guarantees
- **Rerunnable:** every stage is idempotent; rerun overwrites only its own outputs
  in `output/`. Source files are opened read-only.
- **Auditable:** timestamps on every row/file; `pipeline.log`; source path on every
  fact; confidence scores; explicit REVIEW REQUIRED instead of guesses.
- **Portable:** pure stdlib core; optional libs strictly enhance coverage.
- **AI optional:** deterministic by default; AI extraction is a future add-on that
  must write confidence + audit rows (keys never in code).
