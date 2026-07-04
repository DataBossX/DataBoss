# QA CHECKLIST — Grocery Report

Run through this before delivering. `[T]` = covered by automated tests
(`py -m pytest tests/test_grocery_pipeline.py`).

## Integrity / non-fabrication
- [ ] `[T]` No field is populated that isn't present in a source document (unfound = blank).
- [ ] `[T]` Every row in `extracted_facts.csv` has a non-empty `source_file`.
- [ ] Every fact in the draft report traces to a file + page/sheet/row.
- [ ] `REVIEW REQUIRED` / low-confidence rows are visibly flagged, not silently trusted.

## Data preservation
- [ ] No source file was deleted or overwritten (originals untouched).
- [ ] `[T]` Duplicates are only *planned* unless `--apply-quarantine` is passed.
- [ ] With `--apply-quarantine`, only byte-identical dupes moved; a canonical copy remains.

## Completeness (all stage outputs present)
- [ ] `[T]` A: `file_inventory.csv/.xlsx`
- [ ] `[T]` B: `duplicate_candidates.csv`, `quarantine_plan.csv`
- [ ] `[T]` C: `extracted_text/`, `source_text_index.csv`
- [ ] `[T]` D: `document_classification.csv`
- [ ] `[T]` E: `extracted_facts.csv/.xlsx`
- [ ] `[T]` F: `reconciliation_table.xlsx`, `chain_summary.xlsx`, `conflicts_and_gaps.xlsx`
- [ ] `[T]` G: `validation_report.xlsx`, `review_required.csv`
- [ ] `[T]` H: `Grocery_Report_DRAFT.md/.docx`, `Executive_Summary.md`, `Curative_List.xlsx`, `Source_Index.xlsx`
- [ ] `[T]` I: `status_dashboard.html/.xlsx`
- [ ] Every output shows a generation timestamp.

## Correctness (seeded-defect detection)
- [ ] `[T]` Exact duplicate file is detected.
- [ ] `[T]` Impossible date (e.g. 2099) is flagged red.
- [ ] `[T]` Per-tract decimals not summing to 1.0 are flagged.
- [ ] `[T]` Known parties/dates/instruments are captured from clean documents.
- [ ] `[T]` Documents with no royalty/decimal do NOT get invented values.

## Text-extraction coverage (real run)
- [ ] `source_text_index.csv` reviewed: files with `status=no-text` are scans → OCR them.
- [ ] PDF/OCR backends installed if any scanned instruments are present.

## Reconciliation sanity (real run)
- [ ] Tracts in `chain_summary.xlsx` match the section(s) the report covers.
- [ ] Every conflict in `conflicts_and_gaps.xlsx` has a plausible cause and a next action.

## Rerun / audit
- [ ] `[T]` Pipeline reruns into the same output dir without error (idempotent).
- [ ] `run_manifest.json` reviewed (counts, deps present, warnings/errors = 0 expected).

## Security
- [ ] No API keys, secrets, or credentials in code or in any output file.
- [ ] No document content uploaded anywhere; everything stays local under `./output`.
