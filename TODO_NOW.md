# TODO NOW — Grocery Report (to Monday, July 6 2026)

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
- [x] Inventoried repo; determined pipeline state (no ingestion pipeline existed).
- [x] Built `grocery_report_pipeline.py` (stages A–I), rerunnable & non-destructive.
- [x] Synthetic corpus + 10 passing end-to-end tests.
- [x] Planning docs, QA checklist, runbook, requirements.

## Risk (Monday)
**YELLOW.** Machinery complete and verified on synthetic data. Delivery gated on running
against the real documents locally + human review of flagged items. Turns **RED** only if
the source folder cannot be located or is unreadable; **GREEN** once the real run shows no
red validation issues and the review pass is signed off.
