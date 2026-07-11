# DataBossX Self-Builder (`databossx/`)

The canonical registry generator for the DataBossX system, implementing the
Master Execution Directive's recovery/consolidation outputs.

## What it does

`python -m databossx.build_registry --qa "<test summary>"` scans the repo,
merges the curated knowledge recovered from the Google Drive workspace
(`databossx/data/curated_knowledge.json`), and rebuilds `registry/`:

| File | Contents |
|---|---|
| `MASTER_INVENTORY.jsonl` | every asset (repo scan + Drive snapshot): path, sha256, size, capabilities |
| `CAPABILITY_REGISTRY.json` | capability → implementing assets (CAP_OCR, CAP_WI, CAP_QA, …) |
| `PROJECT_GRAPH.json` | client → project → report relationships |
| `KNOWLEDGE_GRAPH.json` | typed nodes/edges: project, county, section, leases, wells, tracts, document sets, open items |
| `MASTER_BUILD_QUEUE.json` | ranked backlog + prioritized open items |
| `TOOLS.json` / `PROMPTS.json` / `REPORTS.json` / `CLIENTS.json` | typed registries |
| `QA_REPORT.json` | test-suite result recorded at build time |
| `CHANGELOG.md` | append-only build log |

## Rules encoded

- **Recover before rebuilding** — the curated knowledge file records what
  already exists (Drive workspace tools, prompts, report versions) and marks
  superseded versions instead of deleting them.
- **Evidence before assumptions** — every curated fact carries a `source`
  field naming the recovered document it came from. Ownership/WI/NRI values
  are never stated; the canonical report status is
  "PRESENT OWNERSHIP NOT ESTABLISHED" until the evidence gates close
  (see `open_items` in `MASTER_BUILD_QUEUE.json`).
- **Capabilities before folders** — repo assets are classified by capability
  rules in `build_registry.py` (`CAPABILITY_RULES`).
- **Tests before promotion** — `tests/test_databossx_registry.py` covers
  output completeness, hash integrity, classification, graph referential
  integrity, determinism, and the no-fabricated-ownership rule.

## Updating

- New repo tools are picked up automatically by the scan; add a
  `CAPABILITY_RULES` entry if the default classification is wrong.
- New workspace facts (reports, open items, wells, leases) go in
  `databossx/data/curated_knowledge.json` with a `source` reference.
- Rerun the module and commit the regenerated `registry/`.
