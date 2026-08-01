# DataBossX

DataBossX is a local-first toolkit for evidence-grounded land and mineral title research, document extraction, exact interest calculation, human review, and versioned report production.

The repository contains public-safe code and synthetic fixtures for:

- `src/databossx/command_brain/` — voice-first Command Brain Alpha: policy engine, tool registry, model gateway, agent dispatch, tournaments, and an append-only receipt ledger (stdlib only, synthetic fixtures only)
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

Command Brain Alpha:

- [Architecture](docs/COMMAND_BRAIN_ARCHITECTURE.md)
- [Threat model](docs/COMMAND_BRAIN_THREAT_MODEL.md)
- [Local model setup](docs/COMMAND_BRAIN_LOCAL_MODEL_SETUP.md)
- [Voice setup](docs/COMMAND_BRAIN_VOICE_SETUP.md)
- [Implementation report and controlled-demo receipt](docs/COMMAND_BRAIN_IMPLEMENTATION_REPORT.md)
- [Rollback](docs/COMMAND_BRAIN_ROLLBACK.md)

```bash
python -m databossx.command_brain.demo    # controlled demo, synthetic data only
```

## Public repository boundary

This public repository must not contain real client manifests, exact project legal descriptions, source-drive identifiers, evidence hashes, owner data, title chains, workbooks, job queues, QA reports, release receipts, or private runtime telemetry. Real work stays in approved private repositories and controlled cloud storage.

Unreviewed output is draft work product, not a certified abstract, title opinion, or substitute for a qualified title examiner or licensed attorney.

## Tests

```bash
python -m pytest -q
```

See `horizon/README.md`, `RUNBOOK.md`, and `REPORT_PIPELINE_PLAN.md` for subsystem instructions.
