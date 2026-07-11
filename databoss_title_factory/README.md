# DataBoss Title Factory

A focused local evidence engine for the Section 32-11N-25W, Beckham County
workflow. It inventories a project without reorganizing it, creates multiple
derived image variants, retains OCR geometry, archives every extraction pass,
reconciles fields against source support, and creates a preservation-audited
review package.

The current code can prepare the workflow, but this repository does not contain
the private Section 32 courthouse images, client template, or report candidates.
It therefore cannot produce or claim a completed client report in the cloud.

## Windows quick start

1. Double-click `SETUP_DATABOSS_TITLE_FACTORY.bat`.
2. Install the Tesseract OCR desktop program if setup reports that it is absent.
3. Double-click `RUN_DATABOSS_TITLE_FACTORY.bat`.
4. Enter the source project folder and Excel template in the left control desk.
5. Run the five buttons from left to right.

Setup creates `.venv`, activates it for the setup window, and installs the local
dependencies. The run launcher activates the same environment every time.

## Safety model

- Source folders are read-only. The pipeline never deletes, renames, moves, or
  overwrites a source file.
- Every run is written beneath
  `<project>/DataBoss_Title_Factory_Output/runs/<timestamp>`.
- Weak OCR and instrument results are copied into the run's `quarantine` folder.
  They are retained for examiner review and are also represented in the missing
  document schedule.
- OCR blocks retain source hash, page, derived image, preprocessing recipe,
  engine/configuration, confidence, and bounding coordinates where available.
- Extracted fields carry field-level source provenance. External candidates
  lacking current-run source hashes and provenance cannot be accepted.
- Every independent candidate and losing interpretation is retained in an
  immutable archive with a SHA-256 hash.
- Excel export copies the selected `.xlsx` or `.xlsm` without adding worksheets.
  Runsheet, conflict, confidence, model, and audit data go into a separate
  `DATABOSS_CONTROL_WORKBOOK.xlsx`.
- A before/after workbook audit checks OOXML parts, worksheets, formulas,
  drawings, images, charts, defined names, merged cells, validation,
  conditional formatting, dimensions, print settings, and protection.
- OpenPyXL is not represented as a perfect preservation engine. High-risk
  features are reported, and preservation is claimed only when the audit passes.
- Values beginning with Excel formula-control characters are escaped before
  export.

## Tournament inputs

The Extract button always produces both:

- `candidates/cursor_output.json` and `.csv`
- `candidates/codex_output.json` and `.csv`

By default, these are built by two independent deterministic local parsing
strategies. To reconcile actual Cursor and Codex output, provide their JSON
paths in **Tournament inputs**. Accepted JSON forms are an array of instrument
objects, one object, or an object containing `instruments`, `results`, or
`rows`.

Useful fields are:

`instrument_number`, `instrument_type`, `instrument_date`, `recorded_date`,
`book`, `page`, `grantor`, `grantee`, `legal_description`,
`interest_conveyed`, `lease_royalty_terms`, `confidence`, `citation`,
`source_path`, and `source_locator`.

The source controls. Agreement is not proof. Material disagreement in parties,
identifiers, dates, legal, interest, or lease terms remains unresolved and goes
to human review. Every candidate remains in `candidate_archive.jsonl`.

## Excel output

Export creates a timestamped `FINAL_DATABOSS_OUTPUT_*` review package with:

- an exact `UNTOUCHED_TEMPLATE_COPY`
- an exact, unpopulated `CLIENT_REPORT_CANDIDATE`
- a separate `DATABOSS_CONTROL_WORKBOOK.xlsx`
- before/after workbook inventories and preservation audit
- copied control data and candidate archive
- package manifest and readiness statement

The candidate is deliberately not populated until an approved writable-range
mapping and the real Section 32 evidence are available. The readiness statement
therefore says `NOT READY TO SUBMIT`.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r databoss_title_factory/requirements.txt
pytest tests/test_databoss_title_factory.py -q
streamlit run databoss_title_factory/app.py
```
