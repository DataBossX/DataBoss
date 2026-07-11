# DataBossX

DataBossX is a local-first title evidence and report-processing system. This
repository is the canonical integration candidate for the existing Horizon,
Grocery Report, DOTO Image Commander, and web prototypes.

## Controlled foundation

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

## Existing engines

- `horizon/`: exact-fraction title chaining, validation, repair, and versioning.
- `grocery_report_pipeline.py`: broad intake, extraction, reconciliation, and
  draft report pipeline.
- `doto_image_commander/`: county image acquisition and review workflow.
- `automation/`: county research and workbook automation.
- `backend/` and `frontend/`: prototype web application.

These systems are not yet fully integrated. In particular, a real client report
cannot be produced without the authoritative source set and approved workbook
template. AI output must not be treated as examiner-approved merely because
deterministic checks pass.

## Security

Real `.env` files are ignored. Copy an `.env.example` locally and inject secrets
through the deployment environment or a secret vault. CI rejects common
credential forms in tracked files. Any credential that has ever been committed
must still be revoked and rotated; deleting it from the current tree does not
remove it from Git history.

## Verification

```bash
python scripts/scan_secrets.py
pytest
```
