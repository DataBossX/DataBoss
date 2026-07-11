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

## Important status

This checkout contains code and synthetic fixtures, not the private title
corpus. It cannot produce a defensible real title report until the relevant
source documents are inventoried and processed on the authorized local machine.
Unreviewed output is draft work product, not a certified abstract, title
opinion, or substitute for a qualified title examiner or licensed attorney.

## Existing test suites

```bash
python -m pytest -q
```

See `horizon/README.md`, `RUNBOOK.md`, and `REPORT_PIPELINE_PLAN.md` for the
existing subsystem instructions.
