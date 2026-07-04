# REPORT PIPELINE PLAN — Grocery Report

Design of `grocery_report_pipeline.py`. The pipeline is deterministic, rerunnable, and
never fabricates legal/title data. Every output carries a generation timestamp; every fact
row carries a source path + page/sheet/row.

## Execution order
`A inventory → C text extraction → B duplicates → D classify → E extract → F reconcile →
G validate → H report → I dashboard` (text extraction runs before dedupe/classify because
those stages consume extracted text).

## A. File inventory
- Recursive walk of `--root`, skipping `.git`, `output`, `node_modules`, `venv`, etc.
- Records: rel/abs path, name, ext, size, modified, **SHA-256**, likely type, status.
- Out: `file_inventory.csv`, `file_inventory.xlsx`.

## B. Duplicate detection (non-destructive)
- **Exact** = identical SHA-256 (keeps earliest-modified as canonical).
- **Probable** = filename similarity ≥ 0.90 (rapidfuzz, else difflib).
- **Near** = extracted-text similarity ≥ 0.92 (length-gated to stay cheap).
- Out: `duplicate_candidates.csv`, `quarantine_plan.csv`. **Nothing is moved by default.**
  `--apply-quarantine` moves only byte-identical dupes into `output/quarantine/`
  (a move, never a delete; the canonical copy is always preserved).

## C. Text extraction (graceful)
- `.txt/.md/.log` direct; `.csv` cell dump; `.xlsx` via openpyxl; `.docx` via python-docx
  then a stdlib zip/XML fallback; `.pdf` via pdfplumber → PyMuPDF → OCR; images via OCR.
- Where no backend is available, writes a note (never crashes) so gaps are visible.
- Out: `extracted_text/<hash>.txt`, `source_text_index.csv` (method, ocr_used, chars, note).

## D. Classification (deterministic)
- Keyword/regex rules over filename + extracted text → one or more of the 15 mission
  categories, with a confidence score; anything without a confident category becomes
  `unknown/review required`. Out: `document_classification.csv`.

## E. Structured extraction (deterministic; AI optional/opt-in)
- Regex capture of parties (grantor/grantee/lessor/lessee/assignor/assignee/decedent),
  effective/execution/recording dates, book·page / instrument no., county/state, legal &
  tract description, gross/net acres, royalty, WI, NRI, decimal interest, depth, term,
  extension/option, reservations. **Every field is nullable — unfound = blank, never
  guessed.** Per-field + overall confidence; review flags for high-value low-confidence
  fields. Out: `extracted_facts.csv`, `extracted_facts.xlsx`.
- **Row-wise ingestion:** spreadsheets, runsheets and ownership/OGL sheets (`.xlsx`,
  `.csv`, `.tsv`) are parsed *by row*, not as a text blob. A header row is detected and
  columns are mapped to fields via a synonym map (`COLMAP`), so each owner/instrument row
  becomes its own fact with a `sheet:<name> row:<n>` anchor. This makes per-tract decimal
  sums and ownership chains precise. Free-text documents still use the regex path.
- **Known limits:** free-text regex extraction is a *cursory* first pass; unusual column
  headers may need a synonym added to `COLMAP`. Legacy `.doc` and image-only PDFs need OCR
  backends installed to yield text.
- **AI extraction (opt-in only):** a hook exists for enriching low-confidence rows via an
  LLM. It is **off by default**, requires `--use-llm` + an API key from the environment
  (never stored in code/outputs), and always records a confidence score and audit note.

## F. Reconciliation / chain engine
- Tracts are grouped by a **canonical Section-Township-Range key** (`canonical_tract`),
  so "Section 12, T7N, R63W", "Sec 12 T7N R63W" and "Section 12, Township 7 North,
  Range 63 West" all reconcile as one tract.
- Party chain, tract/legal-description chain, lease/OGL chain, assignment chain.
- Per-tract acreage + decimal calculations; flags decimals not summing to 1.0 and gross
  acreage disagreements; detects grantor↔grantee continuity gaps.
- Out: `reconciliation_table.xlsx` (5 sheets), `chain_summary.xlsx`, `conflicts_and_gaps.xlsx`.

## G. Validation (13 rules)
missing recording data • inconsistent legal descriptions • inconsistent party names •
impossible dates • duplicate instruments • missing source citations • decimals that don't
sum • lease/OGL rows with no supporting document • facts without classification • high-value
low-confidence fields • acreage mismatches • stale prior-draft data • chain gaps.
Severity = red/yellow/green. Out: `validation_report.xlsx`, `review_required.csv`.

## H. Report assembly
Executive summary, full draft (Markdown + DOCX), title/ownership summary, lease/OGL summary,
assignment chain, curative/exceptions list, calculation notes, unresolved issues, source
index. Out: `Grocery_Report_DRAFT.md/.docx`, `Grocery_Report_Executive_Summary.md`,
`Grocery_Report_Curative_List.xlsx`, `Grocery_Report_Source_Index.xlsx`.

## I. Dashboard
Self-contained HTML (no external assets, no secrets) + XLSX: RAG per stage, % complete,
remaining blockers, Monday delivery-risk banner. Out: `status_dashboard.html/.xlsx`.

## Cross-cutting
- `run_manifest.json` (counts, deps present, warnings/errors) + `extraction_log.csv`.
- Idempotent and safe to rerun. Stdlib-only core; optional deps only improve fidelity.
