# DataBossX

DataBossX is a local-first toolkit for evidence-grounded land and mineral title research, document extraction, exact interest calculation, human review, and versioned report production.

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

A machine-enforced publication-policy gate (`scripts/check_publication_policy.py`) fails CI if any known client identifier, cloud drive ID, private path, owner record, evidence hash, or final/client work product appears in the tracked tree. Gitleaks remains the dedicated credential gate; the publication gate is additional and independent.

Unreviewed output is draft work product, not a certified abstract, title opinion, or substitute for a qualified title examiner or licensed attorney.

## Control plane

The `databossx` package provides the shared operating ledger. All examples below use a
synthetic, non-client fixture (`examples/projects/SYNTHETIC-DEMO/project_manifest.json`,
project `SYNTHETIC-DEMO-001`, `Fictional County`) — never a real project manifest.

- content-addressed assets with every known source location;
- immutable project-manifest revisions that carry the authoritative policy
  (`required_checks` and release policy) forward on every intake;
- evidence records with source, locator, extracted text, conclusion, and
  separate confidence dimensions, classified as confidential content;
- run receipts identifying agent, model, prompt, inputs, outputs, errors, and
  cost, with secrets recursively redacted before persistence;
- immutable QA results;
- hash-chained promotion receipts for
  `SOURCE → STAGING → EXTRACTED → RECONCILED → QA → APPROVED → DELIVERED`;
- mandatory linked evidence and QA before canonical promotion;
- `APPROVED` and `DELIVERED` require an authenticated, single-use, expiring,
  exact-asset-hash and exact-target-state approval record whose signature is
  verified with a trusted public key configured **outside** the database. If no
  trusted verifier is configured, these promotions **fail closed**.

The database stores metadata, not source document bytes. Intake reads and hashes
source files without modifying them, rejecting symlinks, junctions, and any path
that resolves outside the authorized intake/backup root.

```bash
# Configure the trusted approval verifier (public key only; the private key
# never lives in the repository or the database).
export DATABOSSX_APPROVAL_PUBKEYS=./config/approval_authorities.json

python -m databossx --database ./private/control.sqlite3 init
python -m databossx --database ./private/control.sqlite3 \
  create-project examples/projects/SYNTHETIC-DEMO/project_manifest.json
python -m databossx --database ./private/control.sqlite3 \
  --intake-root /path/to/authorized/root \
  intake SYNTHETIC-DEMO-001 /path/to/authorized/root/frozen/sources --source-authority 1
python -m databossx --database ./private/control.sqlite3 \
  verify-ledger SYNTHETIC-DEMO-001
```

Do not commit the control database or client documents. Keep them in an
approved, encrypted, access-controlled data location with restrictive file
permissions, tested backups, retention limits, and a secure-deletion policy.

## Security

Real `.env` files are ignored. Copy an `.env.example` locally and inject secrets
through the deployment environment or a secret vault. CI rejects common
credential forms in tracked files and runs a dedicated Gitleaks gate. Any
credential that has ever been committed must still be revoked and rotated;
deleting it from the current tree does not remove it from Git history. See
[SECURITY.md](SECURITY.md) and the rotation evidence template in
`docs/credential-rotation-evidence.md`.

## Tests and local checks

```bash
python scripts/scan_secrets.py
python scripts/check_publication_policy.py
python -m pytest -q
```

See `horizon/README.md`, `RUNBOOK.md`, and `REPORT_PIPELINE_PLAN.md` for subsystem instructions.
