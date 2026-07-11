# DataBossX

DataBossX is a local-first toolkit for evidence-grounded land and mineral title
research, document extraction, exact interest calculation, human review, and
versioned report production.

The repository currently contains several proven but separate systems:

- `horizon/` — exact interest math, instrument chaining, validation, repair,
  versioning, and examiner worklists
- `grocery_report_pipeline.py` — deterministic inventory-to-report stages A–I
- `doto_image_commander/` — county image acquisition, OCR/vision, queue, costs,
  and audit
- `mineral_deal_room/` — Vite/React operational UI prototype
- `backend/` and `frontend/` — legacy document-processing demo

The unification decision, safety rules, title workflow, migration sequence, and
acceptance gates are in:

- [DataBossX OS Blueprint](docs/DATABOSSX_OS_BLUEPRINT.md)
- [Machine-readable build plan](docs/architecture/databossx-os.build-plan.json)
- [Security and mandatory credential rotation](SECURITY.md)

## Control plane

The `databossx` package provides the shared operating ledger:

- content-addressed assets with every known source location;
- immutable project-manifest revisions;
- evidence records with source, locator, extracted text, conclusion, and
  separate confidence dimensions;
- run receipts identifying agent, model, prompt, inputs, outputs, errors, and
  cost;
- immutable QA results;
- hash-chained promotion receipts for
  `SOURCE → STAGING → EXTRACTED → RECONCILED → QA → APPROVED → DELIVERED`;
- mandatory linked evidence and QA before canonical promotion;
- explicit human approval for `APPROVED` and `DELIVERED`.

The database stores metadata, not source document bytes. Intake reads and hashes
source files without modifying them.

```bash
python -m databossx --database ./private/control.sqlite3 init
python -m databossx --database ./private/control.sqlite3 \
  create-project examples/beckham-section-32.manifest.json
python -m databossx --database ./private/control.sqlite3 \
  intake OK-BECKHAM-32-11N-25W /path/to/frozen/sources --source-authority 1
```

Do not commit the control database or client documents. Keep them in an
encrypted, access-controlled data location with independently tested backups.

## Important status

This checkout contains code and synthetic fixtures, not the private title
corpus. It cannot produce a defensible real title report until the relevant
source documents are inventoried and processed on the authorized local machine.
Unreviewed output is draft work product, not a certified abstract, title
opinion, or substitute for a qualified title examiner or licensed attorney.

## Security

Real `.env` files are ignored. Copy an `.env.example` locally and inject secrets
through the deployment environment or a secret vault. CI rejects common
credential forms in tracked files. Any credential that has ever been committed
must still be revoked and rotated; deleting it from the current tree does not
remove it from Git history.

## Existing test suites

```bash
python scripts/scan_secrets.py
python -m pytest -q
```

See `horizon/README.md`, `RUNBOOK.md`, and `REPORT_PIPELINE_PLAN.md` for the
existing subsystem instructions.
