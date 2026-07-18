# DataBossX

DataBossX is a local-first toolkit for evidence-grounded land and mineral title research, document extraction, exact interest calculation, human review, and versioned report production.

## Start here: the Command Center

`databossx/` is the unified application that ties the engines below into **one
project-based command** producing client-ready **Excel + PDF + a dashboard**:

```bash
python dbx.py doctor    # self-check
python dbx.py demo      # build + run a synthetic project end to end
python dbx.py run --project horizon --root /path/to/files
```

One-click launchers: **`DataBossX.bat`** (Windows, menu-driven) / `run_databossx.sh`.
Operator quick start: [`DATABOSSX_COMMAND_CENTER.md`](DATABOSSX_COMMAND_CENTER.md).
Package details: [`databossx/README.md`](databossx/README.md).

The repository contains public-safe code and synthetic fixtures for:

- `databossx/` — **Command Center**: project orchestration, exact mineral/WI/NRI economics, Excel+PDF+dashboard, self-check, backups
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

## Tests

```bash
python -m pytest -q
```

See `horizon/README.md`, `RUNBOOK.md`, and `REPORT_PIPELINE_PLAN.md` for subsystem instructions.
