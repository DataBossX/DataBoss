# DataBossX

DataBossX is a local-first toolkit for evidence-grounded land and mineral title research, document extraction, exact interest calculation, human review, and versioned report production.

The repository contains public-safe code and synthetic fixtures for:

- `src/databossx/` — trusted local kernel, immutable SHA-256 vault, SQLite/FTS evidence index, authenticated loopback API, audit ledger, and Command Center
- `horizon/` — exact interest math, instrument chaining, validation, repair, versioning, and examiner worklists
- `grocery_report_pipeline.py` — deterministic inventory-to-report stages
- `doto_image_commander/` — county image acquisition, OCR/vision, queue, costs, and audit
- `mineral_deal_room/` — operational UI prototype
- `backend/` and `frontend/` — legacy document-processing demo
- `website/` — public marketing site for databossx.com (Astro, static, synthetic data only)

Core controls:

- [DataBossX OS Blueprint](docs/DATABOSSX_OS_BLUEPRINT.md)
- [Machine-readable build plan](docs/architecture/databossx-os.build-plan.json)
- [Data classification and publication policy](docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md)
- [Security and mandatory credential rotation](SECURITY.md)

## Public repository boundary

This public repository must not contain real client manifests, exact project legal descriptions, source-drive identifiers, evidence hashes, owner data, title chains, workbooks, job queues, QA reports, release receipts, or private runtime telemetry. Real work stays in approved private repositories and controlled cloud storage.

Unreviewed output is draft work product, not a certified abstract, title opinion, or substitute for a qualified title examiner or licensed attorney.

## Start on Windows

Double-click `Run_DataBossX.bat`. The first launch creates an isolated Python
environment and opens the local Command Center. Data remains under the ignored
`runtime/` folder and the server refuses non-loopback network binding.

For a safe end-to-end verification without client data:

```bash
python databossx.py --runtime ./runtime demo
```

The demo registers a labeled synthetic project, copies and verifies evidence in
the content-addressed vault, extracts searchable source text, builds draft
reports from vault copies, registers every artifact, and verifies the audit
hash chain. Project source files are never moved, renamed, or overwritten.

## Tests

```bash
python -m pytest -q
```

See `horizon/README.md`, `RUNBOOK.md`, and `REPORT_PIPELINE_PLAN.md` for subsystem instructions.
