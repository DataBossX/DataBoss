# Acceptance Checklist — "Done means done"

The app is accepted only when every box below is checked against the real
Section 31 files. These mirror the user's acceptance tests. No box is "mostly."

## Workbook handling

- [ ] Opens the real target workbook (the Section 31 cursory title `.xlsx`).
- [ ] Identifies all tabs and adds NONE. The detected tab set is exactly:
      Overview, `"Title "` (trailing space preserved), PLAT, OGLs, Runsheet,
      Tract 1, Tract 2, Tract 3, Tract 4, Tract 5, Tract 6, Tract 7, Tract 8,
      WI 1, WI 2, Wells, Title_BACKUP (hidden), Runsheet_BACKUP (hidden).
- [ ] No tab is renamed, reordered, deleted, or unhidden.

## Index reading + queue

- [ ] Reads the 88-page handwritten index PDF (`12N 24W 31 - Index`) using a
      vision-capable LLM (not Tesseract).
- [ ] Builds a processing queue in SQLite (one candidate per instrument).
- [ ] Every handwriting-derived field carries a verification flag.

## Browser review

- [ ] Opens at least one OKCountyRecords document link in the USER'S browser via
      CDP (attaches to the visible, logged-in session — no new headless browser,
      no re-login, no stored credentials).
- [ ] Captures a screenshot / evidence for the opened document.
- [ ] User can take over the browser at any time; app yields cleanly.
- [ ] On CAPTCHA / login / paywall, the app stops and asks for manual handling
      (does not bypass).

## Extraction + writing

- [ ] Extracts the relevant fields for at least one document.
- [ ] Writes into the EXISTING Runsheet format — columns A–N, T, U only.
- [ ] Writes NOTHING to columns O, P, Q, R, S (live formulas untouched).
- [ ] Column K is written as a working `=HYPERLINK(...)` formula.
- [ ] Doc types are normalized while original wording is preserved in Notes (J).

## Uncertainty handling

- [ ] Uncertain reads are flagged in Review (T) and/or NEED/ACTION (U) using the
      defined flag vocabulary (see REFUSE_TO_GUESS.md).
- [ ] The app refuses to guess legal-judgment items (net acres, ownership,
      released/HBP, illegible legals) and flags them instead.

## Output + integrity

- [ ] Saves a NEW workbook copy (the original is never overwritten).
- [ ] Saves a timestamped backup.
- [ ] The saved file opens with NO repair prompt.
- [ ] Sheet names are unchanged (exact match incl. `"Title "` trailing space).
- [ ] Formatting is preserved (matches the reference/format expectations).
- [ ] No broken formulas: O–S still hold formulas; no #REF!, #VALUE!, #NAME?,
      #DIV/0!, #N/A anywhere in the workbook.

## QA + audit

- [ ] Produces a local QA summary (rows written, columns touched, flags raised,
      links opened, output + backup paths, per-check pass/fail).
- [ ] SQLite + JSON audit records what the model saw, what it produced, and every
      human correction with who/when.

## Out of scope (must NOT be claimed as done)

- [ ] Does NOT issue a title opinion or any legal conclusion.
- [ ] Does NOT compute net acres or ownership as authoritative results.
- [ ] Does NOT store, transmit, or require any credentials.
