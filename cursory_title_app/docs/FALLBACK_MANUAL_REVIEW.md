# Fallback / Manual Review Workflow

The app is built to stop and ask for help rather than guess or push through an
access control. This document describes what happens when automation cannot or
should not proceed.

## When manual review is triggered

- **Vision/OCR confidence is low** (and all handwriting reads are low-confidence
  by default).
- **CAPTCHA, login wall, or payment/paywall appears** in the browser.
- **The county viewer breaks** (page won't load, viewer errors, document missing).
- **The scan is unreadable** (too faint/blurred to extract a field).
- **Extraction fails** entirely (status `EXTRACTION_FAILED`).

In every case the rule is the same: **pause, surface, let the human fix it,
record the correction, then (and only then) write to the workbook.**

## The workflow

1. **Pause.** The candidate's status is set to `NEEDS_REVIEW` (or
   `EXTRACTION_FAILED`). No Excel write happens for this candidate.
2. **Surface in the Streamlit UI.** Show the user:
   - the source page image (from the index PDF) and/or the browser screenshot,
   - the model's raw read and confidence (if any),
   - the proposed field values with their flags,
   - the document link.
3. **Human hand-corrects.** The user edits the fields directly in the UI. They can
   accept, change, or clear any value, and add/remove flags from the defined
   vocabulary (see `REFUSE_TO_GUESS.md`).
4. **Record the correction.** Every change is written to the SQLite `correction`
   table with: field, old value, new value, `corrected_by` (the local user), and
   `corrected_at` (timestamp), plus an optional note. The original model output
   and the page image/screenshot remain in the `evidence` table — corrections do
   not erase what the model saw.
5. **Write to the workbook.** Only after human approval does the candidate move to
   `APPROVED` and become eligible for the format-preserving write (A–N, T, U
   only; O–S never touched). The write is logged in `write_log`.

Nothing is written to Excel from a low-confidence, unreviewed, or access-blocked
candidate.

## Manual takeover steps for the browser

When a CAPTCHA / login / payment wall appears, or the viewer breaks, or the user
simply wants to drive:

1. The app detects the block (or the user clicks "Take over") and STOPS
   automating. It does not attempt to solve the CAPTCHA or bypass the wall.
2. The browser is the user's own visible Chrome/Edge session — the user clicks
   into it and handles the step manually (solve CAPTCHA, log in, complete a
   purchase the user chooses to make, navigate the viewer).
3. The app waits. It does not click, type, or navigate while the user is in
   control.
4. When the document is on screen, the user clicks "Capture" in the UI; the app
   takes a screenshot and records it as evidence (still attached over CDP — no
   new session, no stored credentials).
5. The user enters/corrects the fields (steps 3–4 above) and approves.
6. Control returns to the app for the next candidate only when the user advances.

Because the app attaches to the user's already-logged-in session over CDP and
never stores credentials, manual takeover is just the user using their own
browser. There is no session to "lose" and nothing to re-authenticate.

## Audit guarantee

For any manually reviewed row, the SQLite + JSON audit shows the full chain:
what the model saw (page image / screenshot + raw output) -> what it proposed
(with flags) -> what the human changed (field-level, attributed, timestamped) ->
what was written to the workbook. This makes every value in the final Runsheet
traceable.
