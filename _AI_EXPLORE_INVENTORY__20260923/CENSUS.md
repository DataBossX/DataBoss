# Census of `origin/main` at `582d951`

Counting rule: every main figure below is `git ls-tree -r --name-only 582d951` or a `git show 582d951:<path>` read. GitHub figures are `gh issue list` / `gh pr list` against `DataBossX/DataBoss` on 2026-09-23, `--limit 300`. Both lists returned fewer rows than the limit, so they are treated as complete for that endpoint.

The Search API was not used. A probe of `search/issues` with `is:issue is:open` returned pull-request numbers (32, 59, 95–116) and a total of 24, which matches the open-PR list, not the issue list. Those search totals are discarded. They are not zeros and they are not the census.

## Headline counts (main `582d951`)

| Item | Count | Rule |
| --- | ---: | --- |
| Tracked files | 227 | `git ls-tree -r 582d951` |
| Python files (`*.py`) | 80 | suffix |
| Python files that are tests under `tests/` | 19 | path prefix `tests/` |
| Pytest test functions | 119 static; collected count UNKNOWN | lines equal to `^def test_` inside `tests/test_*.py` only |
| GitHub Actions workflows | 3 | `.github/workflows/*` |
| Markdown files | 17 | `*.md` |
| Files under `docs/` | 3 | path prefix |
| SQL migrations | 1 | `migrations/*.sql` |
| SQL tables created by that migration | 20 tables + 1 FTS5 virtual table | `CREATE TABLE` / `CREATE VIRTUAL TABLE` in `001_initial_schema.sql` |
| UI apps | 4 | package or app entry with a user-facing surface (defined below) |
| Open GitHub issues | 15 | `gh issue list --state open` |
| Closed GitHub issues | 2 | `gh issue list --state closed` |
| Open pull requests | 24 | `gh pr list --state open` |
| Open drafts | 18 | `isDraft=true` |
| Open non-drafts | 6 | `isDraft=false` |
| Merged pull requests | 10 | `gh pr list --state merged` |
| Closed unmerged pull requests | 65 | 75 closed PR rows minus 10 merged |

Closed PR list length was 75. Merged list length was 10. 75 − 10 = 65 closed-unmerged. This arithmetic assumes the two lists do not overlap. That assumption was not re-checked row by row, so the 65 is derived, and a hand audit of the closed-unmerged set was not done.

Pytest was not executed. Five `pytest.mark.parametrize` markers exist under `tests/` on this commit, so a collected test count can be higher than 119. Collected count remains UNKNOWN, not zero. `backend_test.py` and `.devcontainer/playwright_test.py` contain zero `def test_` lines.

## Python files by top directory (80)

| Location | Files | What it is on main |
| --- | ---: | --- |
| `src/databossx/` | 8 | Canonical foundation package from merged PR #50. Modules: `__init__.py`, `api.py`, `config.py`, `database.py`, `hashing.py`, `intake.py`, `models.py`, `orchestrator.py`. Version string `0.1.0`. |
| `horizon/` | 19 | Exact interest math, chaining, validation, workbook QA, repair, controlled loop, audit. |
| `tests/` | 19 | 17 `test_*.py` plus `conftest.py` and `__init__.py`. |
| `doto_image_commander/` | 22 | Streamlit county-image app, including page modules and package `__init__.py` files. |
| `automation/` | 5 | `parsing.py`, `writer.py`, `status_logic.py`, `playwright_bot.py`, `roger_mills_title_report_builder.py`. |
| `backend/` | 2 | `server.py`, `external_integrations/__init__.py`. |
| repository root | 3 | `grocery_report_pipeline.py`, `make_sample_data.py`, `backend_test.py`. |
| `.devcontainer/` | 2 | `playwright_executor.py`, `playwright_test.py`. |

8 + 19 + 19 + 22 + 5 + 2 + 3 + 2 = 80.

`src/databossx/governor/` is absent at `582d951`. `pyproject.toml` is absent at `582d951`.

## Test modules and static `def test_` counts

| File | `def test_` |
| --- | ---: |
| `tests/test_horizon_interest.py` | 12 |
| `tests/test_horizon_controlled_loop.py` | 10 |
| `tests/test_grocery_pipeline.py` | 10 |
| `tests/test_horizon_review_fixes.py` | 9 |
| `tests/test_horizon_validation.py` | 8 |
| `tests/test_horizon_review_fixes3.py` | 8 |
| `tests/test_horizon_versioning.py` | 7 |
| `tests/test_horizon_pipeline.py` | 7 |
| `tests/test_horizon_chaining.py` | 7 |
| `tests/test_horizon_audit_fixes.py` | 7 |
| `tests/test_horizon_foundation.py` | 6 |
| `tests/test_horizon_review_fixes6.py` | 5 |
| `tests/test_horizon_review_fixes5.py` | 5 |
| `tests/test_horizon_review_fixes2.py` | 5 |
| `tests/test_horizon_repair_orchestrator.py` | 5 |
| `tests/test_horizon_artifacts.py` | 5 |
| `tests/test_databossx_foundation.py` | 3 |
| Total | 119 |

Foundation tests on main cover WAL bootstrap, content-addressed vault copy, and one intake/inventory/template path. They do not cover policy, leases, claims, routing, receipts, or Issue #94 regressions.

## Workflows (3)

| File | Name in file | Trigger | Permissions observed |
| --- | --- | --- | --- |
| `.github/workflows/python-app.yml` | Python application | push and pull_request to `main` | `contents: read` |
| `.github/workflows/secret-scan.yml` | Secret scan | push and pull_request | `contents: read`; current-tree gitleaks in a read-only container |
| `.github/workflows/website-ci.yml` | Website CI | push/PR path-filtered to `website/**` | `contents: read` |

No CodeQL workflow, dependency-review workflow, or branch-protection snapshot is in the tree. Issue #72's required security docs are absent on main (see gaps). Absence of a workflow file does not prove the GitHub setting is off. Org and repo settings were not read. Those settings are UNKNOWN, not disabled.

## Docs

Markdown files (17):

- `README.md`
- `PROJECT_STATUS.md`
- `TODO_NOW.md`
- `REPORT_PIPELINE_PLAN.md`
- `QA_CHECKLIST.md`
- `RUNBOOK.md`
- `SECURITY.md`
- `test_result.md`
- `docs/DATABOSSX_OS_BLUEPRINT.md`
- `docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md`
- `frontend/README.md`
- `horizon/README.md`
- `horizon/CONTROLLED_LOOP.md`
- `prompts/extractor_user.md`
- `prompts/reasoner_user.md`
- `website/README.md`
- `website/FINAL_WEBSITE_UPGRADE_REPORT.md`

`docs/` itself holds those two policy/architecture markdown files plus `docs/architecture/databossx-os.build-plan.json`.

Not on main, and required by later issues:

- `docs/security/REPOSITORY_SECURITY_BASELINE.md`
- `docs/security/REPOSITORY_RULESET_SNAPSHOT.json`
- `docs/security/CI_PERMISSION_MATRIX.md`
- `docs/security/SECRET_INCIDENT_CLOSURE_CHECKLIST.md`
- `docs/continuous_improvement/CANONICAL_OVERLAP_MATRIX.md`
- `docs/continuous_improvement/CANONICAL_COMPONENT_MAP.json`
- `docs/continuous_improvement/FIRST_CYCLE_TASK_ENVELOPE.json`
- `docs/continuous_improvement/PHASE0_RECEIPT.md`
- `docs/CANONICAL_SYSTEM_MAP.md` (named by Issue #28)

`website/docs/qa/` holds 15 PNG screenshots. Those are not counted as markdown.

`config/` on main is one file: `config/settings.toml`. It is a scraper settings file, not `config/policies/`. The build-plan directory `config/policies` is absent. This census does not repeat values from that settings file.

## Migrations (1)

`migrations/001_initial_schema.sql` only.

`DataBossDatabase.initialize` reads that one path. It does not scan `migrations/*.sql` and it does not record a schema version.

Tables: `jurisdictions`, `projects`, `title_projects`, `source_connections`, `source_snapshots`, `assets`, `asset_versions`, `derived_artifacts`, `artifact_lineage`, `workbook_templates`, `writable_ranges`, `workflow_definitions`, `runs`, `tasks`, `task_dependencies`, `task_attempts`, `task_leases`, `approvals`, `outbox_events`, `audit_events`, plus virtual `audit_events_fts`.

Indexes and insert triggers exist for audit FTS. No Python caller on this commit inserts `outbox_events` or `task_leases`. Those tables are schema-only.

## UI apps (4)

Counted as a UI app only when the tree has a user-facing front end:

| App | Stack | Evidence |
| --- | --- | --- |
| `frontend/` | Create React App (`react-scripts`) | `package.json` name `frontend`, scripts `start` / `build` / `test` |
| `mineral_deal_room/` | Vite + React + TypeScript | `package.json` name `mineral-deal-room`, `vite.config.ts`, pages under `src/pages/` including review, evidence, audit |
| `website/` | Astro | `package.json` name `databossx-website` |
| `doto_image_commander/` | Streamlit multipage | `app.py` plus `pages/1_Import.py` through `pages/6_Settings.py` |

Not counted as UI apps:

- `backend/server.py` is a FastAPI process, not a UI. It is a fifth application surface.
- `horizon/` is a CLI/library pipeline.
- `src/databossx/api.py` is a second FastAPI factory (`/healthz`, `/projects/{id}`, `/projects/{id}/assets`) with no host bind of its own.

The blueprint asks for one Vite/React TypeScript interface. The closest shell is `mineral_deal_room/`. `frontend/` is the CRA app the build plan marks for retirement. `website/` is the marketing site merged in PR #42.

`mineral_deal_room/src/data/sampleData.ts` is still present. Live canonical API wiring was not found in this census.

## Control API and foundation behavior on main

Public functions exported by `src/databossx/__init__.py`: `DataBossConfig`, `DataBossDatabase`, `create_project`, `inventory_source`, `register_source_connection`, `register_workbook_template`, `seed_project_intake_run`.

Intake creates a project in status `DRAFT`, a `title_projects` row in release state `DRAFT`, a read-only source connection, copies bytes into `runtime/projects/<id>/vault/sha256/<prefix>/<hash>` when the destination is missing, and seeds three tasks (`REGISTER_SOURCES`, `INVENTORY_AND_LOCK`, `REGISTER_TEMPLATE`) directly in state `READY`. Run status is stored as `PLANNED`. There is no transition function, lease claim, heartbeat, or idempotency key.

Vault copy uses a temp file and `os.replace`. It does not delete the source. It does not re-hash the vault object after the replace.

## Open issues (15)

| Issue | Title |
| --- | --- |
| [#94](https://github.com/DataBossX/DataBoss/issues/94) | P0 CORRECTNESS / SECURITY — fail-closed current-main integrity repairs |
| [#93](https://github.com/DataBossX/DataBoss/issues/93) | SECURITY / PUBLICATION HOLD — quarantine client-shaped PRs and converge open draft lineages |
| [#81](https://github.com/DataBossX/DataBoss/issues/81) | Build fail-forward autonomous Section 32 orchestrator and final-report repair loop |
| [#79](https://github.com/DataBossX/DataBoss/issues/79) | Section 32 evidence closure and champion report completion lanes |
| [#78](https://github.com/DataBossX/DataBoss/issues/78) | Harden Control Tower for durable exactly-once Section 32 execution |
| [#72](https://github.com/DataBossX/DataBoss/issues/72) | P0: Prove repository security baseline before any consolidation merge |
| [#71](https://github.com/DataBossX/DataBoss/issues/71) | P0: Complete read-only release reviews for Penterra Sections 17 and 20 |
| [#70](https://github.com/DataBossX/DataBoss/issues/70) | P0: Reconcile Section 32 controlling workbook, V13 authority, and protected hashes |
| [#69](https://github.com/DataBossX/DataBoss/issues/69) | Phase 0: Canonical overlap inventory and first bounded improvement cycle |
| [#68](https://github.com/DataBossX/DataBoss/issues/68) | Build the DataBossX Continuous Improvement Governor |
| [#64](https://github.com/DataBossX/DataBoss/issues/64) | Post-acceptance hardening: close PR #60 title-integrity risks before next automated report run |
| [#63](https://github.com/DataBossX/DataBoss/issues/63) | P0: Validate review packets without altering title evidence |
| [#56](https://github.com/DataBossX/DataBoss/issues/56) | P0: Consolidate overlapping DataBossX PRs into one canonical release train |
| [#28](https://github.com/DataBossX/DataBoss/issues/28) | P0 Execution Board: Canonicalize DataBossX and release Beckham 32 safely |
| [#2](https://github.com/DataBossX/DataBoss/issues/2) | [Security] Your zhipu API key was committed to this repo |

Closed issues returned by the same command: #41 and #38 only.

Issue #94 remained OPEN at the end of this census. A later local commit message that says the issue is closed does not change that GitHub state.

## Open pull requests (24)

Non-draft (6), higher accidental-merge risk:

| PR | Title | Files | Delta |
| --- | --- | ---: | --- |
| [#107](https://github.com/DataBossX/DataBoss/pull/107) | Add routed engine: batching, cache, candidate comparison, and sealed receipts | 15 | +1789 / −42 |
| [#109](https://github.com/DataBossX/DataBoss/pull/109) | Add a read-only portfolio QA dashboard builder | 7 | +660 / −0 |
| [#103](https://github.com/DataBossX/DataBoss/pull/103) | Enforce fail-closed abstract package validation | 75 | +31436 / −119 |
| [#101](https://github.com/DataBossX/DataBoss/pull/101) | Horizon Section 7 SW/4 - Deep Title Reconstruction and Current Ownership Audit | 5 | +288 / −0 |
| [#97](https://github.com/DataBossX/DataBoss/pull/97) | feat(section7): Section 7 Title Engine, Google Drive Sync & Multi-Pass Report Pipeline | 9 | +3270 / −0 |
| [#95](https://github.com/DataBossX/DataBoss/pull/95) | Section 32 Challenger Submission & DataBossX Best Moves Implementation | 33 | +2548 / −10 |

Draft (18): #116, #115, #114, #113, #112, #111, #110, #108, #106, #105, #104, #102, #100, #99, #98, #96, #59, #32.

Focused donor states rechecked at the end of this pass:

| PR | State | Draft | Role in this packet |
| --- | --- | --- | --- |
| [#114](https://github.com/DataBossX/DataBoss/pull/114) | OPEN | yes | Trusted-kernel + Issue #94 + read-only Drive sync. 37 files, +2477 / −441. Head `cursor/trusted-kernel-drive-sync-21ab`. |
| [#116](https://github.com/DataBossX/DataBoss/pull/116) | OPEN | yes | Challenger notes only. 4 files, +670 / −0, all under `_AI_CURSOR_GROK_4_6_DATABOSSX_CHALLENGER__20260923/`. |
| [#110](https://github.com/DataBossX/DataBoss/pull/110) | OPEN | yes | `source_bound_finish/` toolkit. 19 files, +1736 / −4. |
| [#107](https://github.com/DataBossX/DataBoss/pull/107) | OPEN | no | Routed engine. 15 files, +1789 / −42. |
| [#50](https://github.com/DataBossX/DataBoss/pull/50) | MERGED | no | Foundation now on main. Merge commit is `582d951`. Merged 2026-07-18. |

## Merged pull requests (10)

| PR | Merged | Title |
| --- | --- | --- |
| #50 | 2026-07-18 | Canonical foundation (this baseline) |
| #42 | 2026-07-15 | Website v2 |
| #31 | 2026-07-12 | Contain client-specific metadata in the public repository |
| #30 | 2026-07-11 | Controlled workbook QA loop |
| #27 | 2026-07-11 | Operating system architecture and security baseline docs |
| #19 | 2026-07-04 | Grocery Report pipeline |
| #18 | 2026-07-04 | Horizon pipeline |
| #15 | 2026-06-27 | Roger Mills builder + CI fix |
| #14 | 2026-06-27 | Roger Mills builder |
| #3 | 2026-05-28 | DOTO Image Commander |

PR #26 and PR #25, named by the blueprint as the Title Factory and the generic Horizon report, are CLOSED, unmerged, and titled parked / do-not-merge. Same parked state for the Issue #68 donor set #51, #52, #54, #61, #66, #67.

## Blueprint entity coverage on main

The build plan lists 48 entity names (27 core + 21 title). Tables or rows on main cover 17 of those names in a partial way: Project, SourceConnection, SourceSnapshot, Asset, AssetVersion, DerivedArtifact, WorkflowDefinition, Run, Task, TaskDependency, TaskAttempt, TaskLease (table only), Approval (table only), AuditEvent, TitleProject, Jurisdiction, and a partial WritableRangeApproval (`writable_ranges` plus `workbook_templates`).

Unmapped on main: EvidenceSpan, Claim, ClaimSupport, Conflict, WorkerCapability, ReviewGate, ReviewDecision, Artifact, ArtifactVersion, ModelRouteDecision, ToolDefinition, ToolRun, SearchScope, Tract, LegalDescription, Instrument, InstrumentParty, RecordingReference, InstrumentClaim, ChainLink, InterestLedgerEntry, Lease, Assignment, Well, HBPFact, TitleException, CurativeItem, ExaminerIssue, MissingDocument, WorkbookCandidate, WorkbookIntegrityAudit.

Horizon implements several of those ideas in memory and workbooks (interest fractions, chain links, validation issues). They are not the canonical SQLite entities.

## Target layout from the build plan

Present on main: `src/databossx/` (flat, not the planned subpackages), `migrations/`, `tests/` (flat, not `unit` / `integration` / `adversarial` / `golden`).

Absent on main: `src/databossx/control`, `domain`, `vault`, `connectors`, `memory`, `routing`, `workers`, `products/title`, `products/doto`, `products/deals`, `src/databossx/api` as a package, `ui/`, `config/policies`, `tests/unit`, `tests/integration`, `tests/adversarial`, `tests/golden`, `runtime/` (runtime is created at intake time and is gitignored by use, not committed).

## Workspace drift (not part of the counts above)

While this census was running, the shared checkout moved off `582d951`.

Observed after the move:

- `origin/main` still `582d951`
- `origin/cursor/kernel-governor-tournament-7f1f` at `3149ead11d95801f0332312a0dee2218203f0ede` (2026-09-23 19:44:57Z), two commits ahead of main: `7440ee3` "Add conservative publication policy scanner" and `3149ead` "Close Issue #94 fail-closed defects and add the improvement governor."
- The checkout in this environment was `cursor/self-improving-evolution-loop-6072`, also at `3149ead`, with further uncommitted edits under `src/databossx/`, `tests/`, and new untracked docs. Those edits were still changing during the census. Their contents are UNKNOWN relative to a stable tree and are excluded from every count above.

`3149ead` is not main. Its commit message does not close Issue #94 on GitHub. It does add paths that collide with PR #114 (`grocery_report_pipeline.py`, `horizon/repair.py`, `backend/server.py`, `src/databossx/database.py`, `src/databossx/__init__.py`) and a third `migrations/002_*.sql` (`002_governor.sql`). See the matrix.
