# Grocery Report — QA Checklist

Run this before handing the report to Rodney as final. Anything unchecked =
not final. Automated checks live in `output/validation_report.csv`; the rest are
human spot-checks.

## Integrity / no-fabrication
- [ ] Every row in `extracted_facts.csv` has a non-empty `source_file`.
- [ ] No high-value field (decimal, net acres, royalty, NRI, WI, legal) is
      populated with `confidence < 0.6` without a REVIEW REQUIRED flag.
- [ ] Blank fields are genuinely "not in source" (spot-check 5 against originals).
- [ ] No source file was modified or deleted (compare `file_inventory.sha256`
      before/after — hashes unchanged).

## Duplicates
- [ ] `duplicate_candidates.csv` reviewed; exact dupes confirmed by sha256.
- [ ] `quarantine_plan.csv` approved; approved dupes moved to `quarantine/`.
- [ ] Pipeline **rerun** after quarantine so decimal sums exclude duplicates.

## Extraction / classification
- [ ] `source_text_index.csv` has no unexpected `error` / `needs_dependency`
      rows (install missing libs and rerun if so).
- [ ] `needs_ocr` rows either OCR'd (Tesseract) or explicitly deferred with note.
- [ ] `document_classification.csv` unknown/review rows triaged.

## Reconciliation
- [ ] Each tract's `decimal_sum` in `reconciliation_table.csv` is ~1.0 or has a
      documented reason (e.g., partial interest, outstanding conveyance).
- [ ] Every `chain_summary.csv` gap_flag resolved or noted as curative.
- [ ] `conflicts_and_gaps.csv` is empty or every item appears in the curative list.

## Report outputs
- [ ] `Grocery_Report_DRAFT.md` (and `.docx` if generated) opens and reads cleanly.
- [ ] `Grocery_Report_Executive_Summary.md` counts match the detailed tables.
- [ ] `Grocery_Report_Curative_List.csv/.xlsx` covers all open items.
- [ ] `Grocery_Report_Source_Index.csv/.xlsx` lists every source file + hash.
- [ ] `status_dashboard.html` posture is understood and acceptable for delivery.

## Reproducibility
- [ ] `python -m unittest tests.test_report_pipeline` passes.
- [ ] Two consecutive full runs produce the same fact/reconciliation results.
- [ ] All outputs carry a `generated_at` timestamp.
