# DataBossX

DataBossX is a local-first toolkit for evidence-grounded land and mineral title research, document extraction, exact interest calculation, human review, and versioned report production.

The current DataBoss Title Intelligence implementation is a review-workflow framework. It provides read-only source inventory, hashing, local OCR, cited deterministic extraction, conflict quarantine, exact fraction calculations, workbook-preservation checks, local role-based authentication, and versioned artifacts. It does **not** autonomously establish title, render a legal opinion, certify an abstract, or make a report client-ready. The real Section 32 corpus is not mounted in this repository environment and has not been processed here.

The repository contains public-safe code and synthetic fixtures for:

- `horizon/` — exact interest math, instrument chaining, validation, repair, versioning, and examiner worklists
- `grocery_report_pipeline.py` — deterministic inventory-to-report stages
- `doto_image_commander/` — county image acquisition, OCR/vision, queue, costs, and audit
- `mineral_deal_room/` — operational UI prototype
- `backend/` and `frontend/` — legacy document-processing demo

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

Windows operators should begin with [installation](docs/operations/INSTALL_WINDOWS.md) and the [start/stop/backup runbook](docs/operations/START_STOP_BACKUP.md). Architecture, security, title-methodology, user, reviewer, and developer documents are under `docs/`. `IMPLEMENTATION_REPORT.md` and `completion.json` record the verified implementation state and disclosed limitations.
