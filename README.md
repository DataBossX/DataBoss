# DataBossX

DataBossX is a local-first toolkit for evidence-grounded land and mineral title research, document extraction, exact interest calculation, human review, and versioned report production.

The repository contains public-safe code and synthetic fixtures for:

- `horizon/` — exact interest math, instrument chaining, validation, repair, versioning, and examiner worklists
- `grocery_report_pipeline.py` — deterministic inventory-to-report stages
- `doto_image_commander/` — county image acquisition, OCR/vision, queue, costs, and audit
- `mineral_deal_room/` — operational UI prototype
- `backend/` and `frontend/` — legacy document-processing demo
- `website/` — public marketing site for databossx.com (Astro, static, synthetic data only)

## Landman Helper (connected title-intelligence system)

The Landman Helper wires the previously-standalone engines into one workflow:
upload title documents → deterministic extraction (`grocery_report_pipeline`) →
exact fraction chain-of-title reconciliation, over-conveyance detection, and
validation (`horizon`) → a current mineral-ownership ledger with net acres and an
examiner worklist, persisted as an auditable `derived_artifact` in the DataBossX
foundation (`src/databossx`). Nothing is fabricated: unsupported balances are
tagged `Needs Examiner Review`.

- Engine: `src/databossx/title_intelligence.py` (pure, unit-tested).
- API: `backend/landman_api.py`, mounted at `/api/landman/*` by `backend/server.py`.
- UI: the "⚖️ Landman" tab in `frontend/` (dark command-center theme).

Real document formats are supported end to end: PDFs (text layer via
`pdfplumber`/`PyMuPDF`), Word `.docx` (via `python-docx`), and scanned
images/PDFs (OCR via `pytesseract`). PDF-text and Word extraction need only the
Python packages; **image / scanned-PDF OCR also requires the `tesseract-ocr`
system binary** (`sudo apt-get install -y tesseract-ocr`). When a backend is
missing, or OCR mangles a value, the field is left blank and flagged for examiner
review — never fabricated. If you install these backends into a running backend,
restart it so the extractors are re-detected.

Try it locally (backend on `:8001`, frontend on `:3000`), then open the Landman
tab and click **Load Demo Project** for a synthetic, public-safe walkthrough, or
`curl -X POST localhost:8001/api/landman/demo`. You can also upload real
`.pdf`/`.docx`/image deeds. The reconciled analysis exports to a canonical
cursory-title-report `.xlsx` and an examiner-worklist `.csv` (the "⬇️" buttons in
the report panel, or `GET /api/landman/projects/{id}/report.xlsx` and
`/worklist.csv`). Tests: `python -m pytest tests/test_title_intelligence.py
tests/test_landman_document_formats.py -q`.

Core controls:

- [DataBossX OS Blueprint](docs/DATABOSSX_OS_BLUEPRINT.md)
- [Machine-readable build plan](docs/architecture/databossx-os.build-plan.json)
- [Data classification and publication policy](docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md)
- [Security and mandatory credential rotation](SECURITY.md)

## Public repository boundary

This public repository must not contain real client manifests, exact project legal descriptions, source-drive identifiers, evidence hashes, owner data, title chains, workbooks, job queues, QA reports, release receipts, or private runtime telemetry. Real work stays in approved private repositories and controlled cloud storage.

Unreviewed output is draft work product, not a certified abstract, title opinion, or substitute for a qualified title examiner or licensed attorney.

## Tests

```bash
python -m pytest -q
```

See `horizon/README.md`, `RUNBOOK.md`, and `REPORT_PIPELINE_PLAN.md` for subsystem instructions.
