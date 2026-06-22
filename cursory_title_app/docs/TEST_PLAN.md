# Test Plan

Tests use the actual Section 31 files. Identify them in `config.py`:

- **Target workbook** — the real cursory title `.xlsx` to be edited (with live
  O–S formulas and the fixed tab set).
- **Reference / format workbook** — a known-good workbook used to assert
  formatting/format expectations and as a diff baseline.
- **Index PDF** — `12N 24W 31 - Index`, 88 pages, handwritten cursive, no text
  layer.

Test data principle: never run destructive tests against the original target.
Always copy it into a temp dir first. The original is read-only ground truth.

## Unit tests

### Column map (`runsheet/columns.py`)
- `test_column_map_a_to_u` — every column A..U maps to the documented field.
- `test_writable_allowlist` — writable set is exactly
  `{A,B,C,D,E,F,G,H,I,J,K,L,M,N,T,U}`.
- `test_formula_columns_forbidden` — `{O,P,Q,R,S}` are NOT in the writable set.

### Formula-cell protection (`excel/guard.py`)
- `test_write_to_O_raises` ... `test_write_to_S_raises` — any attempt to write
  O, P, Q, R, or S raises and aborts the write (no partial write).
- `test_write_to_unknown_tab_raises` — writing to a sheet not in the fixed set
  raises.
- `test_title_sheet_trailing_space_preserved` — the `"Title "` sheet name is
  matched literally with its trailing space; not trimmed.

### SQLite store (`db/store.py`)
- `test_insert_candidate_and_read_back`.
- `test_status_transitions` — NEW -> EXTRACTED -> NEEDS_REVIEW -> APPROVED ->
  WRITTEN, plus EXTRACTION_FAILED and REJECTED paths.
- `test_evidence_linked_to_candidate`.
- `test_correction_records_who_and_when` — corrections store user + timestamp.
- `test_write_log_records_columns_and_files`.

### Pydantic schemas (`schemas.py`)
- `test_valid_extraction_parses`.
- `test_missing_required_field_flags_not_crashes` — illegible/missing fields
  produce a flag, not an exception.
- `test_doc_type_normalization` — abbreviations map per
  `DOCTYPE_NORMALIZATION.md` and original wording is preserved into Notes.
- `test_no_oms_fields_in_schema` — schema does not expose O–S as settable.

### PDF render (`index/render.py`)
- `test_render_page_count` — renders 88 pages from the real index PDF.
- `test_render_returns_image_bytes` — each page yields a non-empty image.
- `test_render_specific_page` — a single requested page renders.

## Integration tests

All run against a COPY of the real target workbook.

### Round-trip preservation (the critical one)
- `test_roundtrip_tab_list_unchanged` — open the copy, write a sample candidate
  row (A–N, T, U), save a NEW file; reopened tab list equals exactly:
  `["Overview", "Title ", "PLAT", "OGLs", "Runsheet", "Tract 1", "Tract 2",
  "Tract 3", "Tract 4", "Tract 5", "Tract 6", "Tract 7", "Tract 8", "WI 1",
  "WI 2", "Wells", "Title_BACKUP", "Runsheet_BACKUP"]` — order, names, count,
  and hidden flags all unchanged.
- `test_roundtrip_OS_formulas_intact` — O,P,Q,R,S on touched rows still contain
  formula strings (assert `cell starts with "="`, not cached values).
- `test_roundtrip_no_error_values` — scan all sheets for `#REF!`, `#VALUE!`,
  `#NAME?`, `#DIV/0!`, `#N/A`; none present.
- `test_roundtrip_only_allowed_columns_changed` — diff edited rows vs the
  reference; only A–N, T, U differ.
- `test_roundtrip_hyperlink_formula` — column K cell is a valid
  `=HYPERLINK(...)` pointing at the intended URL.
- `test_no_repair_prompt` — saved file opens cleanly (via COM, opening with no
  recovery dialog; in CI without Excel, validate the zip/XML is well-formed).
- `test_source_not_modified` — original target file hash unchanged after the run.

### COM vs openpyxl parity
- `test_com_and_openpyxl_write_same_cells` — both writers target the same
  A–N/T/U cells; both preserve the tab set and leave O–S formulas in place.
  (COM test is Windows + Excel only; skip with a clear marker elsewhere.)

### Index -> queue -> diff
- `test_vision_candidates_enter_queue` — extracted candidates land in SQLite with
  low-confidence flags on handwriting fields.
- `test_diff_against_existing_runsheet` — candidates already present in the
  existing Runsheet are marked as matches, not duplicated.

## Live manual test (run on the user's Windows machine)

Prerequisites: Chrome/Edge launched with `--remote-debugging-port=9222`, user
logged into OKCountyRecords.

Steps:
1. Start the user's browser with remote debugging and log in to OKCountyRecords.
2. Launch the app (`run.bat`) and open the Streamlit UI.
3. Pick one candidate with a document link.
4. Trigger "open in browser." Confirm the app attaches over CDP and the existing
   visible tab/window navigates to the document — no new headless browser, no
   re-login.
5. Confirm a screenshot is captured and surfaced in the UI and recorded in the
   evidence store.
6. Manually grab control of the browser; confirm the app yields cleanly.
7. If a CAPTCHA / login / payment wall appears, confirm the app STOPS and prompts
   for manual handling (does not try to bypass it).

Pass criteria: the document opens in the user's own session, no credentials are
entered by the app, the evidence is recorded, and takeover works.

## QA summary check

After an integration run, assert `qa/verify.py` emits a local JSON summary with:
rows written, columns touched per row, flags raised (by type), links opened,
backup file path, output file path, and pass/fail for each preservation check.
