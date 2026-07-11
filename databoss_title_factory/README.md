# DataBoss Title Factory

A local Streamlit production line for cited title-document extraction. It scans
project folders, pre-processes images, runs OCR, extracts instrument candidates,
reconciles Cursor and Codex candidate output, quarantines weak results, builds
draft schedules, and exports a template-preserving Excel workbook.

## Windows quick start

1. Double-click `Setup_DataBoss_Title_Factory.bat`.
2. Install the Tesseract OCR desktop program if setup reports that it is absent.
3. Double-click `Run_DataBoss_Title_Factory.bat`.
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
- Every fact retains `source_path`, `source_locator`, and a human-readable
  `citation`.
- Excel export first copies the selected `.xlsx` or `.xlsm` template to a
  versioned destination. Existing template sheets are preserved. Generated
  sheets are added only to the copy.
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

Conflicts are resolved field-by-field using normalized agreement and candidate
confidence. Disagreements are recorded; unsupported values remain blank.

## Excel output

The exported workbook preserves the template and adds:

- `DBTF Runsheet`
- `DBTF Missing Docs`
- `DBTF OGL Draft`
- `DBTF Tract Drafts`
- `DBTF Run Manifest`

These are drafts. Quarantined or incomplete facts require title-examiner review.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r databoss_title_factory/requirements.txt
pytest tests/test_databoss_title_factory.py -q
streamlit run databoss_title_factory/app.py
```
