# Cursory Title App — Architecture

## What this is

A **local-first Windows desktop tool** that helps a human finish a cursory title
report workbook for **Section 31, Township 12N, Range 24W, Roger Mills County,
Oklahoma**. It does NOT replace the title examiner. It drafts the Runsheet,
surfaces evidence, and preserves uncertainty for human review.

Everything runs on the user's own Windows machine. Nothing is hosted. There is
no server component. There is no cloud database. The only outbound network
calls are (a) optional LLM API calls for vision extraction and (b) the user's
own browser hitting county record sites that the user is already logged into.

## Hard constraints (these drive every design decision)

1. **Runsheet columns O, P, Q, R, S are LIVE EXCEL FORMULAS.** The writer must
   ONLY write to **A–N, T, U**. It must NEVER touch O–S. (O=GROSS ACRES,
   P=INTEREST IN, Q=INTEREST OUT, R=TOTAL/Net Ac Conveyed, S=Calc Basis/Flags.)
2. **Tabs are frozen.** Never add, rename, reorder, or delete any sheet.
   The tab set is fixed (see "Workbook contract" below).
3. **Exact format preservation.** Open and edit the real `.xlsx`; never rebuild
   it from a blank file. `pandas.to_excel` and any other "regenerate the sheet"
   approach is rejected.
4. **No credentials.** The app drives the user's already-open, already-logged-in
   browser via CDP. It never stores, reads, or transmits passwords. It never
   bypasses CAPTCHA, paywalls, or access controls.
5. **Handwriting is low-confidence by default.** Every read off the 88-page
   handwritten cursive index is flagged for human verification.

## Workbook contract (the fixed tab set)

These tabs must exist and must remain exactly as-is — same names, same order,
nothing added or removed:

```
Overview
"Title "        <- NOTE: trailing space in the sheet name is intentional
PLAT
OGLs
Runsheet
Tract 1
Tract 2
Tract 3
Tract 4
Tract 5
Tract 6
Tract 7
Tract 8
WI 1
WI 2
Wells
Title_BACKUP     <- hidden
Runsheet_BACKUP  <- hidden
```

The sheet name `"Title "` has a trailing space. Match it literally. Do not
trim, normalize, or "fix" it.

## Runsheet column map (A–U)

| Col | Field | Writable by app? |
|-----|-------|------------------|
| A | Instrument # | YES |
| B | OGL | YES |
| C | Doc Type | YES |
| D | Bk/Pg. | YES |
| E | Effective Date | YES |
| F | Recorded Date | YES |
| G | Grantor | YES |
| H | Grantee | YES |
| I | Legal Description | YES |
| J | Notes | YES |
| K | Document Link (`=HYPERLINK(...)`) | YES (as formula) |
| L | Tract(s) | YES |
| M | Conveyance type | YES |
| N | Conveyance Amount (decimal) | YES |
| **O** | **GROSS ACRES** | **NO — live formula** |
| **P** | **INTEREST IN** | **NO — live formula** |
| **Q** | **INTEREST OUT** | **NO — live formula** |
| **R** | **TOTAL (Net Ac Conveyed)** | **NO — live formula** |
| **S** | **Calc Basis / Flags** | **NO — live formula** |
| T | Review | YES |
| U | NEED / ACTION | YES |

The writer enforces this at the code level: the only legal target columns are a
hard-coded allowlist `{A,B,C,D,E,F,G,H,I,J,K,L,M,N,T,U}`. Any attempt to write
O–S raises and aborts the write.

## Data flow

```
 [88-page handwritten index PDF]
            |
            v
   (1) PDF render to page images  --------- index/
            |
            v
   (2) Vision LLM extraction       --------- models/ + index/
       (per-page -> candidate rows,
        every read low-confidence)
            |
            v
   (3) SQLite work queue           --------- db/
       (one row per candidate
        instrument, status=NEW)
            |
            v
   (4) Diff vs existing Runsheet   --------- runsheet/
       (what's already entered vs
        what's new/changed)
            |
            v
   (5) Browser doc review (CDP)    --------- browser/
       open county doc link in the
       user's visible browser;
       optionally screenshot
            |
            v
   (6) Field extraction + validate --------- models/ + schemas.py
       (Pydantic schema; doc-type
        normalization; flags)
            |
            v
   (7) Format-preserving Excel write -------- excel/
       (COM primary / openpyxl fallback;
        only A–N, T, U)
            |
            v
   (8) QA pass                     --------- qa/
       (tab list unchanged, O–S
        formulas intact, no #REF/
        #VALUE/#NAME, link sanity)
            |
            v
   [NEW workbook copy + timestamped backup + QA summary]
```

The whole loop is observable in a local Streamlit UI (`ui/`), where the user
approves, edits, or rejects each candidate before anything is written.

## Component responsibilities

- **`config.py`** — paths to the target workbook, reference/format workbook, the
  index PDF, output directory, model-provider selection, CDP endpoint
  (`http://localhost:9222` by default), confidence thresholds.
- **`schemas.py`** — Pydantic models for an extracted instrument/runsheet row,
  for vision-extraction candidates, and for evidence/audit records. All LLM
  output is validated through these before it can reach the queue or Excel.
- **`models/`** — the model-abstraction layer (see below). Vision OCR, text
  extraction, normalization helpers, with provider swap + retry/fallback.
- **`db/`** — SQLite schema + access layer for the work queue and evidence store.
- **`index/`** — PDF rendering (page -> image), page-range management, sending
  pages to the vision layer, collecting candidate rows.
- **`runsheet/`** — the Runsheet domain logic: column map, existing-row reader,
  diff engine (existing vs candidate), doc-type normalization.
- **`excel/`** — the format-preserving writer. COM (pywin32) primary,
  openpyxl fallback. Enforces the A–N/T/U allowlist and the frozen tab set.
- **`browser/`** — Playwright CDP connection to the user's visible browser;
  navigate to a doc link, screenshot, hand control back to the user.
- **`qa/`** — post-write verification: reopen the saved file, assert tab list,
  assert O–S still hold formulas, scan for error values, emit QA summary.
- **`ui/`** — Streamlit app: queue view, per-candidate review/edit, screenshot
  surfacing, manual-correction capture, write trigger, QA summary view.

## Folder structure

```
cursory_title_app/
├── config.py
├── schemas.py
├── models/
│   ├── __init__.py
│   ├── base.py            # provider interface (extract / vision / normalize)
│   ├── anthropic_provider.py
│   ├── openai_provider.py
│   ├── gemini_provider.py
│   ├── local_ocr_provider.py   # Tesseract — print only, not cursive
│   └── router.py          # provider selection, retry, fallback chain
├── db/
│   ├── __init__.py
│   ├── schema.sql
│   └── store.py           # queue + evidence access layer
├── index/
│   ├── __init__.py
│   ├── render.py          # PDF page -> image
│   └── extract.py         # page image -> candidate rows (via models/)
├── runsheet/
│   ├── __init__.py
│   ├── columns.py         # the A–U map + writable allowlist
│   ├── reader.py          # read existing Runsheet rows
│   ├── diff.py            # existing vs candidate
│   └── normalize.py       # doc-type normalization
├── excel/
│   ├── __init__.py
│   ├── com_writer.py      # pywin32 / Excel COM (PRIMARY)
│   ├── openpyxl_writer.py # fallback
│   └── guard.py           # tab-set + column-allowlist enforcement
├── browser/
│   ├── __init__.py
│   ├── cdp.py             # connect to visible browser over CDP
│   └── review.py          # navigate, screenshot, takeover
├── qa/
│   ├── __init__.py
│   └── verify.py          # post-write checks + QA summary
├── ui/
│   ├── __init__.py
│   └── app.py             # Streamlit
├── docs/
└── run.bat                # Windows launcher
```

## Model abstraction layer + fallback logic

`models/base.py` defines a provider interface:

```
class ModelProvider(Protocol):
    def vision_extract(self, image_bytes, prompt) -> RawExtraction: ...
    def text_extract(self, text, prompt)        -> RawExtraction: ...
    def available(self) -> bool: ...
```

Providers: Anthropic (Claude), OpenAI (GPT-4o class), Gemini, and a local OCR
provider (Tesseract). Tesseract is included only for completeness — it is
print-oriented and **fails on cursive**, so the handwritten index requires a
vision-capable LLM.

`models/router.py` resolves the active provider from `config.py` and runs a
fallback chain:

1. Try the configured primary vision provider.
2. On transient error (timeout, rate limit, 5xx): retry with backoff (e.g. 3
   tries).
3. On hard failure or `available() == False`: fall through to the next provider
   in the chain.
4. If all vision providers fail: the candidate is queued with status
   `EXTRACTION_FAILED` and routed to manual review — never silently dropped,
   never written to Excel.

Confidence handling: vision providers return a confidence/uncertainty signal
per field. Anything below the configured threshold (and **all** handwriting
reads regardless of threshold) gets a flag in the candidate and lands in the
Review (T) / NEED-ACTION (U) columns when written. See `REFUSE_TO_GUESS.md`.

For current Claude model IDs, pricing, and capabilities used to configure the
Anthropic provider, consult the live Anthropic docs / the `claude-api`
reference rather than hard-coding remembered values.

## Local evidence store (SQLite) schema

A single local SQLite DB holds the work queue and the evidence/audit trail.
Sketch (see `db/schema.sql` for the authoritative version):

```sql
-- One candidate instrument / runsheet row in flight.
CREATE TABLE candidate (
    id              INTEGER PRIMARY KEY,
    instrument_no   TEXT,
    source_page     INTEGER,        -- page in the index PDF
    status          TEXT NOT NULL,  -- NEW, EXTRACTED, EXTRACTION_FAILED,
                                    -- NEEDS_REVIEW, APPROVED, WRITTEN, REJECTED
    doc_type_raw    TEXT,           -- as printed/abbreviated in the county index
    doc_type_norm   TEXT,           -- normalized (see DOCTYPE_NORMALIZATION.md)
    payload_json    TEXT,           -- validated extraction (Pydantic dump)
    confidence      REAL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Evidence: what the model saw, what it said, what the human did.
CREATE TABLE evidence (
    id              INTEGER PRIMARY KEY,
    candidate_id    INTEGER NOT NULL REFERENCES candidate(id),
    kind            TEXT NOT NULL,  -- PAGE_IMAGE, MODEL_RAW, SCREENSHOT,
                                    -- DOC_LINK, HUMAN_CORRECTION
    provider        TEXT,           -- which model produced it (if any)
    image_path      TEXT,           -- on-disk path to page image / screenshot
    detail_json     TEXT,           -- raw model output, link, etc.
    created_at      TEXT NOT NULL
);

-- Every human correction, attributed and timestamped.
CREATE TABLE correction (
    id              INTEGER PRIMARY KEY,
    candidate_id    INTEGER NOT NULL REFERENCES candidate(id),
    field           TEXT NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    corrected_by    TEXT NOT NULL,  -- user identity (local)
    corrected_at    TEXT NOT NULL,
    note            TEXT
);

-- One record per Excel write, for audit.
CREATE TABLE write_log (
    id              INTEGER PRIMARY KEY,
    candidate_id    INTEGER REFERENCES candidate(id),
    target_row      INTEGER,
    columns_written TEXT,           -- e.g. "A,B,C,...,N,T,U"
    output_file     TEXT,
    backup_file     TEXT,
    method          TEXT,           -- COM or OPENPYXL
    qa_passed       INTEGER,
    written_at      TEXT NOT NULL
);
```

A parallel JSON audit log mirrors the key events for portability.

## Security model

- **No credential handling.** The app connects to a browser the user already
  launched and logged into (CDP, e.g. `--remote-debugging-port=9222`). It never
  enters passwords, never reads cookies for exfiltration, never persists session
  tokens.
- **No access-control bypass.** If a page shows CAPTCHA, a login wall, or a
  paywall, the app stops and hands control to the user (see
  `FALLBACK_MANUAL_REVIEW.md`). It does not attempt to defeat any control.
- **User can take over at any time.** The browser is visible; the user can grab
  the mouse/keyboard mid-run. The app yields cleanly.
- **Local-only data.** Page images, screenshots, the SQLite DB, and output
  workbooks live on the user's disk. The only network egress is LLM API calls
  (which the user configures and can disable in favor of a local provider) and
  the user's own browsing.
- **Least-write Excel.** The writer can only target the A–N/T/U allowlist and
  can only touch known tabs. This is enforced in code, not just convention.

## Excel preservation strategy (the part that breaks workbooks if done wrong)

The target workbook has live formulas (O–S), specific formatting, hidden backup
sheets, and possibly VBA/links. The goal is: open it, set a handful of cell
values and one hyperlink per row, save — with **zero** collateral change.

**PRIMARY: Windows Excel COM via pywin32.**
- Launch Excel (`win32com.client.Dispatch("Excel.Application")`), open the real
  `.xlsx`, set only the specific cells on the `Runsheet` sheet, set hyperlink
  cells via the formula string (`=HYPERLINK(...)`), then `SaveAs` a NEW copy.
- This uses Excel's own engine, so formulas recalc correctly and formatting,
  styles, hidden sheets, and links are preserved exactly. Requires Excel
  installed on the Windows machine. This only runs on Windows.

**FALLBACK: openpyxl with `keep_vba=True` and `keep_links=True`.**
- `load_workbook(path, keep_vba=True, keep_links=True)`, write ONLY the input
  cells, never rebuild from blank, `save()` to a NEW copy.
- Caveat: openpyxl does not recalc formulas; O–S values will be stale until the
  file is opened in Excel. QA accounts for this by verifying the formula
  *strings* in O–S are intact (not their cached values).

**REJECTED: any tool that rebuilds the workbook** — `pandas.to_excel`,
write-from-scratch openpyxl, CSV round-trips, or anything that does not load and
preserve the original file. These destroy formulas, formatting, hidden sheets,
and links.

**Always output a NEW file** (never overwrite the source) plus a timestamped
backup, so the original is untouched and every run is recoverable.

Both browser automation (CDP) and Excel COM run **only on the user's Windows
machine**. There is no headless/server execution path for either.
