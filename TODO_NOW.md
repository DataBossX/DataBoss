# TODO NOW — Operating Priorities & Best Moves Status

> **Status 2026-08-30:** All automated cloud-executable best moves have been executed and verified.
> Full pytest suite: **154 passed, 0 failed**. Pipeline `--self-test`: **PASS**.
> Section 32 Challenger Package: **Completed, verified, and packaged**.
> See detailed report in `docs/BEST_MOVES_2026-08-30.md`.

## For Rodney (must happen on the machine with the documents)
1. **[BLOCKER] Run the pipeline on the real folder.** One command:
   ```
   py grocery_report_pipeline.py --root "D:\DataBoss\DataBossX_Final_Modular"
   ```
   (Install once: `py -m pip install -r requirements-grocery.txt`.)
2. Open `output\status_dashboard.html` — read the RAG status and Monday risk banner.
3. Work the **red** rows in `output\review_required.csv` first, then the yellow rows.
4. Have a title professional confirm every `REVIEW REQUIRED` fact against its cited source.
5. Confirm duplicates in `output\quarantine_plan.csv`. To move byte-identical dupes into
   `output\quarantine\` (nothing is ever deleted): rerun with `--apply-quarantine`.

## For the automation team (optional accuracy upgrades before Monday)
- [ ] Install PDF/OCR backends so scanned instruments yield text:
      `py -m pip install pdfplumber PyMuPDF pytesseract Pillow` (+ Tesseract binary).
- [ ] If a real ownership spreadsheet exists, tune the header map / decimal columns
      (see `REPORT_PIPELINE_PLAN.md` §E "Known limits").
- [ ] Add county-/section-specific classification keywords if the corpus needs them.
- [ ] (Optional, opt-in) wire the AI extraction hook for low-confidence rows — requires an
      API key in the environment and `--use-llm`; always writes confidence + audit note.

## Done this session
- [x] Standardized `pyproject.toml` and root `pytest.ini` for reproducible environments.
- [x] Added FastAPI control plane tests (`tests/test_databossx_api.py`) and Section 32 Challenger tests (`tests/test_section32_challenger.py`).
- [x] Executed full workspace test suite: 154 passed.
- [x] Verified `grocery_report_pipeline.py --self-test` end-to-end.
- [x] Produced Section 32 13-sheet challenger workbook, dual PDFs, 11 CSV ledgers, and comprehensive qualification reports.
- [x] Published `docs/BEST_MOVES_2026-08-30.md` triaging PR backlog and detailing next operator steps.

## Risk
**GREEN (Cloud Machinery) / YELLOW (Physical Corpus Ingestion).** All cloud machinery is healthy and verified across 154 tests. Physical delivery remains gated on running against the real Windows documents locally.

