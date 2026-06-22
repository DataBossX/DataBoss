# Agent Build Prompts

Seven ready-to-paste prompts, one per component. Each restates the constraints
that component must respect. Hand each to an AI coding agent (or a human) to
build that slice. Shared non-negotiables appear in every prompt because agents
do not read other agents' prompts.

Shared facts referenced below: target is **Section 31, T12N, R24W, Roger Mills
County, OK**. Runsheet columns: A=Instrument #, B=OGL, C=Doc Type, D=Bk/Pg.,
E=Effective Date, F=Recorded Date, G=Grantor, H=Grantee, I=Legal Description,
J=Notes, K=Document Link (`=HYPERLINK`), L=Tract(s), M=Conveyance type,
N=Conveyance Amount, O=GROSS ACRES, P=INTEREST IN, Q=INTEREST OUT, R=TOTAL,
S=Calc Basis/Flags, T=Review, U=NEED/ACTION. **O–S are live formulas — never
write them. Writable: A–N, T, U only.** Fixed tabs (never add/rename/reorder/
delete): Overview, `"Title "` (trailing space), PLAT, OGLs, Runsheet, Tract 1..8,
WI 1, WI 2, Wells, plus hidden Title_BACKUP and Runsheet_BACKUP.

---

## (a) Product architect

> You are building a local-first Windows app, "Cursory Title App", that helps a
> human finish a cursory oil-and-gas title workbook for Section 31, T12N, R24W,
> Roger Mills County, OK. It runs entirely on the user's Windows machine — no
> server. Define the module layout, the data flow, and the contracts between
> components.
>
> Data flow: index PDF -> vision extraction -> SQLite work queue -> diff vs the
> existing Runsheet -> browser-based doc review -> field extraction -> format-
> preserving Excel write -> QA -> NEW workbook copy + timestamped backup + QA
> summary.
>
> Modules: `config.py`, `schemas.py`, `models/`, `db/`, `index/`, `runsheet/`,
> `excel/`, `browser/`, `qa/`, `ui/`. Stack: Python 3.11+, Playwright (CDP to a
> visible browser), pywin32/Excel COM (primary) + openpyxl (fallback), SQLite,
> Streamlit, a swappable model-abstraction layer over Claude/OpenAI/Gemini/local
> OCR with retry + fallback, Pydantic for validation, JSON + SQLite audit, a
> `.bat` launcher.
>
> Hard constraints you must enforce in the design: (1) the Excel writer may write
> ONLY columns A–N, T, U on the Runsheet; O–S are live formulas and must never be
> touched; (2) the fixed tab set above must never be added to, renamed, reordered,
> or deleted; (3) workbook edits open and preserve the real `.xlsx` — never
> rebuild from blank, `pandas.to_excel` is rejected; (4) the browser connects via
> CDP to the user's already-logged-in, visible browser — never store or transmit
> credentials, never bypass CAPTCHA/paywalls; (5) handwriting reads are low-
> confidence and must be preserved as flags for human review.
>
> Deliver: module responsibilities, the Pydantic schema shapes, the SQLite
> schema (work queue + evidence + corrections + write log), and the
> provider-interface signature. Do not gold-plate; no auth system, no
> multi-user, no cloud.

---

## (b) Browser automation engineer

> Build the `browser/` module for a local Windows title-research tool. It must
> connect over Chrome DevTools Protocol (CDP) to the user's ALREADY-RUNNING,
> ALREADY-LOGGED-IN, VISIBLE Chrome/Edge (e.g. started with
> `--remote-debugging-port=9222`). Use Playwright's `connect_over_cdp`.
>
> Responsibilities: navigate to a county document link (OKCountyRecords and
> similar), take a screenshot of the document viewer, and surface the page to the
> Streamlit UI. Provide a clean "hand control back to the user" path.
>
> Absolute rules: NEVER launch a fresh headless browser for real runs — always
> attach to the visible session. NEVER store, read for export, or transmit
> credentials or cookies. NEVER attempt to bypass CAPTCHA, login walls, or
> paywalls — if any of those appear, stop, screenshot, and signal the UI to ask
> the user to handle it manually. The user must be able to take over the mouse/
> keyboard at any moment; yield cleanly when they do. This module only runs on
> the user's Windows machine; there is no server execution path.
>
> Deliver: `cdp.py` (connect/attach) and `review.py` (navigate, screenshot,
> detect-and-pause-on-access-control, takeover). Record each opened link and
> screenshot to the SQLite evidence store. Do not auto-fill forms or click
> through purchase flows.

---

## (c) Excel preservation engineer

> Build the `excel/` module for a Windows tool that edits an existing
> oil-and-gas title workbook WITHOUT damaging it. The workbook has live formulas,
> hidden backup sheets, and specific formatting that must survive exactly.
>
> PRIMARY method: Windows Excel COM via pywin32 — Dispatch Excel, open the real
> `.xlsx`, set only specific cell values and the hyperlink formula cells on the
> `Runsheet` sheet, then `SaveAs` a NEW file. Use Excel's own engine so formulas
> recalc and formatting is preserved.
>
> FALLBACK method: openpyxl with `keep_vba=True, keep_links=True` —
> `load_workbook`, write ONLY the input cells, never rebuild from blank, save to a
> NEW file. Note openpyxl will not recalc formulas; document that O–S cached
> values may be stale until reopened in Excel.
>
> REJECTED: `pandas.to_excel`, write-from-scratch openpyxl, CSV round-trips, or
> anything that regenerates the workbook. Do not use them.
>
> Hard rules enforced IN CODE: (1) only write columns A,B,C,D,E,F,G,H,I,J,K,L,M,N,
> T,U on Runsheet — O,P,Q,R,S are live formulas and must be untouchable; any
> attempt to target them raises and aborts. (2) The tab set is fixed — Overview,
> `"Title "` (literal trailing space, do not trim), PLAT, OGLs, Runsheet,
> Tract 1..8, WI 1, WI 2, Wells, hidden Title_BACKUP and Runsheet_BACKUP — never
> add/rename/reorder/delete a sheet. (3) Always output a NEW file plus a
> timestamped backup; never overwrite the source. (4) Column K is written as an
> Excel `=HYPERLINK(...)` formula. The saved file must open with NO repair prompt.
>
> Deliver: `com_writer.py`, `openpyxl_writer.py`, `guard.py` (allowlist + tab-set
> enforcement). Include the write-log record for the SQLite audit.

---

## (d) OCR / vision extraction engineer

> Build the `index/` extraction path for a title tool. Input: an 88-page PDF
> "12N 24W 31 - Index" — a HANDWRITTEN CURSIVE numerical index with NO text
> layer (scans from ~1905 onward). Tesseract OCR fails on cursive; you must use a
> vision-capable LLM (Claude or GPT-4o class) through the project's model-
> abstraction layer.
>
> Responsibilities: render each PDF page to an image (`render.py`); send page
> images to the vision provider with a structured prompt; parse responses into
> candidate Runsheet rows validated by the project Pydantic schema (`extract.py`).
>
> Hard rules: EVERY handwriting read is low-confidence and MUST carry a flag for
> human verification — never present a cursive read as certain. Use the project
> flag vocabulary ("VERIFY: OCR uncertain", "VERIFY: grantor/grantee spelling",
> "NEED: pull clearer image", etc.; see REFUSE_TO_GUESS.md). Do not invent fields
> the document does not contain (e.g. conveyance fractions not stated). When a
> field is illegible, emit the flag, not a guess. Route extraction failures to
> manual review with status EXTRACTION_FAILED — never drop or fabricate a row.
>
> Persist evidence: store each page image and the raw model output in the SQLite
> evidence store linked to the candidate. Deliver `render.py` and `extract.py`.
> Use the model router's retry/fallback; do not hard-code a single provider.

---

## (e) Title / runsheet data-model engineer

> Build `schemas.py` and the `runsheet/` module for an OK cursory title tool.
> Define Pydantic models for an extracted instrument / Runsheet row matching the
> column map (A–U). Build: the column map + the writable allowlist (`columns.py`),
> a reader for existing Runsheet rows (`reader.py`), a diff engine comparing
> existing rows vs new candidates (`diff.py`), and doc-type normalization
> (`normalize.py`).
>
> Doc-type normalization must map county abbreviations to normalized types while
> PRESERVING the original wording in Notes (J). Mapping: O/L=Oil and Gas Lease,
> ASGT=Assignment, PT-ASGT=Partial Assignment, MD=Mineral Deed, QCD/QC=Quitclaim
> (Quitclaim Mineral Deed where context supports), RATIF=Ratification, REL=Release,
> MTG=Mortgage, DEED/WD=Warranty Deed, FD=Final Decree, AFF=Affidavit, ROW=Right
> of Way, COR=Correction, MEMO=Memorandum, ORDER/JUDG/DECREE=court/probate item.
> See DOCTYPE_NORMALIZATION.md.
>
> Hard rules: the column allowlist must expose ONLY A–N, T, U as writable;
> O,P,Q,R,S (GROSS ACRES, INTEREST IN/OUT, TOTAL, Calc Basis/Flags) are live
> formulas and must be marked read-only/forbidden. The model layer must NOT
> compute net acres, ownership, or interest math — those depend on the live
> formulas and on legal judgment; instead set flags ("VERIFY: net acres
> calculation", "NEED: confirm current ownership"). Do not compute or fill O–S.
>
> Deliver the schemas, the column allowlist, reader, diff, and normalizer.

---

## (f) QA / testing engineer

> Build the `qa/` module and the test suite for a Windows title tool that edits an
> existing workbook. After any Excel write, reopen the saved file and assert:
> (1) the tab list is exactly unchanged — Overview, `"Title "` (trailing space),
> PLAT, OGLs, Runsheet, Tract 1..8, WI 1, WI 2, Wells, hidden Title_BACKUP and
> Runsheet_BACKUP, in order, none added/renamed/removed; (2) Runsheet columns
> O,P,Q,R,S still contain FORMULAS (check the formula strings, not cached values);
> (3) no error values anywhere — scan for #REF!, #VALUE!, #NAME?, #DIV/0!, #N/A;
> (4) the file opens with NO repair prompt; (5) column K hyperlinks resolve to the
> intended URLs; (6) only A–N, T, U changed on edited rows.
>
> Build a QA summary (counts written, flags raised, links opened, failures) saved
> locally as JSON.
>
> Tests: unit tests for the column map + the formula-cell protection (attempting
> to write O–S must raise), SQLite store, Pydantic schemas, and PDF render.
> Integration tests that round-trip the REAL Section 31 workbook and assert the
> tab list unchanged + O–S formulas intact + no error values. A documented live
> manual test that opens one OKCountyRecords doc link in the user's browser via
> CDP. See TEST_PLAN.md. Do not use `pandas.to_excel` anywhere.

---

## (g) Security review

> Review the Cursory Title App (a local-first Windows tool driving the user's
> visible browser and editing an Excel workbook). Confirm these properties and
> flag any violation:
>
> - The browser layer attaches via CDP to the user's already-logged-in, VISIBLE
>   browser and NEVER stores, reads-for-export, or transmits credentials/cookies.
> - The app NEVER bypasses CAPTCHA, login walls, or paywalls; it stops and hands
>   control to the user when any access control appears.
> - The user can take over the browser at any time; the app yields cleanly.
> - No data leaves the machine except (a) LLM API calls the user configured and
>   can disable, and (b) the user's own browsing. Page images, screenshots, the
>   SQLite DB, and workbooks stay local.
> - The Excel writer can only target columns A–N, T, U and only known tabs; O–S
>   and the tab set are protected in code.
> - Outputs are always a NEW file plus timestamped backup; the source is never
>   overwritten.
> - The audit trail (SQLite + JSON) records what the model saw, what it produced,
>   and every human correction with who/when.
>
> Report any place where credentials could leak, an access control could be
> bypassed, the source workbook could be mutated, or O–S could be written.
