# Cursory Title App — Section 31 (31-12N-24W, Roger Mills Co., OK)

Local-first assistant that reads the handwritten county **index PDF**, diffs it
against your existing **Runsheet**, opens county-record documents in **your own
logged-in browser**, extracts title fields with a swappable **vision model**,
and writes vetted values back into your **exact** workbook format — without
touching formulas, tabs, or formatting.

> This is a research/drafting assistant. It is **not** a lawyer, does **not**
> issue title opinions, and preserves uncertainty for human review.

## Hard guarantees
- Writes only to Runsheet columns **A–N, T, U**. Never the live-formula columns
  **O–S** (GROSS ACRES / INTEREST IN / INTEREST OUT / TOTAL / Calc Basis).
- Never adds/renames/reorders/deletes tabs. The frozen tab set is enforced and
  verified after every write.
- Never overwrites your source file. Makes a timestamped backup and writes a new
  `*.UPDATED_<ts>.xlsx`. Verifies it opens with no repair prompt, formulas
  intact, no `#REF!/#VALUE!/#NAME?`.
- Excel writer: **Excel COM (pywin32)** is primary on Windows for perfect
  fidelity; **openpyxl** (load + write only target cells, never rebuild) is the
  cross-platform fallback. `pandas.to_excel` is **rejected** — it rebuilds the
  file and destroys formatting.
- Credentials are never stored or read. You log into your own browser; the app
  attaches over CDP and you can take over the window anytime.

## Setup (Windows)
1. Install Python 3.11+, Excel, and Chrome/Edge.
2. `copy .env.example .env` and add `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`).
3. Double-click **`run.bat`** (creates venv, installs deps, launches the UI).
4. In a separate window start your browser with remote debugging and log in:
   ```bat
   chrome.exe --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\CTA\chrome"
   ```

## Workflow
1. **Read index** — render the 88 cursive pages and vision-extract rows (all
   low-confidence, flagged).
2. **Analyze runsheet** — diff index vs existing Runsheet → missing / duplicate /
   conflict → SQLite work queue.
3. **Work queue** — review the queue.
4. **Document review** — open each link in your browser, capture text/screenshot/
   PDF, extract fields (pauses for CAPTCHA/login/paywall → manual takeover).
5. **Write** — vetted values into existing cells; uncertainty goes to Review (T)
   and NEED / ACTION (U).
6. **QA** — verify the produced workbook.

## Index OCR → Runsheet diff (handwritten index)
The Section 31 index is 88 pages of cursive handwriting with no text layer. This
renders each page, reads it with the vision model, and diffs the result against
your existing Runsheet to surface **missing** and **conflicting** instruments.
Resumable (already-extracted pages are skipped).

```bash
# real run (needs ANTHROPIC_API_KEY or OPENAI_API_KEY)
python -m cursory_title_app.index.run "12N 24W 31 - Index.pdf" "31-...xlsx" --provider claude

# offline wiring test, no key:
python -m cursory_title_app.index.run INDEX.pdf WB.xlsx --pages 1-3 --provider mock
```
Output: `_data/index_missing_report.json` (missing / conflict / present counts +
the prioritized pull list). Every handwriting read is low-confidence and flagged.

## Forensic QC audit (existing workbook)
```bash
python -m cursory_title_app.audit.engine "31-...xlsx"
```
Writes `_data/audit_report.md` + `.json`. See `docs/SECTION31_QC_AUDIT.md` for the
current Section 31 result (all 8 tracts balanced; 640/640 acres; each tract 100%).

## Tests
```bash
pip install -r requirements.txt pytest
CTA_TEST_WORKBOOK=/path/to/31-...xlsx pytest cursory_title_app/tests -q
```

See `docs/` for ARCHITECTURE, AGENT_PROMPTS, TEST_PLAN, ACCEPTANCE,
REFUSE_TO_GUESS, FALLBACK_MANUAL_REVIEW, and DOCTYPE_NORMALIZATION.
