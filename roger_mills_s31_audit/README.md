# Section 31-12N-24W Roger Mills — Ownership/Title Report Fix & QA

Reconciliation + QA cleanup of the Section 31 cursory title workbook.

## Deliverables
- `SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT_CLAUDE_FIXED.xlsx` — fixed
  workbook (23 tabs; Overview first; every tract balances exactly; 12/12 QA pass;
  new **Audit Log** and **Review Flags** tabs).
- `SECTION31_12N_24W_ROGER_MILLS_FIX_AUDIT_SUMMARY.txt` — full audit summary.
- `audit_edits.json` — machine-readable list of all 110 cell edits.

## Root cause
The ten Tract sheets (chain ledgers) were already correct and each balanced exactly
to its acreage. Corruption was confined to the Title roll-up — chiefly Tract 2
(221.70 vs 160 ac) from two mis-transcribed literals (Dow Bain JTWROS 63.70→0.00,
Tim Jensen 7.27→9.27) plus 85+ floating-point net-acre artifacts. No ownership,
acreage, lease, assignment, or OGL data was invented; missing-evidence items are
disclosed as open balances / Needs Verification.

## Reproduce
`sources/ORIGINAL_BASE_FILE.xlsx` is the base pulled from Google Drive.
`scripts/fix.py` applies the edits; `scripts/finalize.py` adds the Audit/Review tabs;
`scripts/final_qa.py` runs the 12-check QA gate. Requires `openpyxl`.
