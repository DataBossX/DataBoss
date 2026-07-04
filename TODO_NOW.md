# TODO NOW — Grocery Report (ordered, do top-down)

**Deadline: Monday 2026-07-06.** Owner of risk decisions: Rodney. Everything else: AI.

## 🔴 Blocking (must happen for a real run)
- [ ] **R1. Point the pipeline at the real documents.** Confirm the project root
      (`D:\DataBoss\DataBossX_Final_Modular` or wherever the docs actually live)
      and that the folder is populated.
- [ ] **R2. Install optional parsers** on that machine (one command):
      `pip install -r report_pipeline\requirements.txt`
      Plus the Tesseract binary if there are scanned PDFs (link in RUNBOOK).

## 🟡 Then run + review
- [ ] **R3. First full run:** `RUN_REPORT_PIPELINE.bat` (or the python command in RUNBOOK).
- [ ] **R4. Review `output\duplicate_candidates.csv` + `quarantine_plan.csv`.**
      Approve the quarantine moves (nothing is moved/deleted automatically).
- [ ] **R5. Quarantine approved duplicates, then RERUN** so decimal sums aren't
      inflated by duplicate instruments.
- [ ] **R6. Work `output\review_required.csv`** (high-severity) top to bottom.
- [ ] **R7. Work `output\conflicts_and_gaps.csv`** (chain gaps, decimal mismatches).
- [ ] **R8. Spot-check `output\extracted_facts.csv`** for the highest-value tracts —
      confirm grantor/grantee/decimal/legal against the linked source file.

## 🟢 Finish
- [ ] **R9. Regenerate report** after fixes (rerun); confirm dashboard trends green.
- [ ] **R10. Hand Rodney:** `Grocery_Report_DRAFT.md/.docx`,
      `Grocery_Report_Executive_Summary.md`, `Grocery_Report_Curative_List.xlsx`,
      `Grocery_Report_Source_Index.xlsx`, `status_dashboard.html`.

## Nice-to-have if time allows
- [ ] Enable AI-assisted extraction for low-confidence rows (keys required; audited).
- [ ] Tune classification keywords / field regexes to the real document wording.
- [ ] Add county-specific instrument-number patterns.
