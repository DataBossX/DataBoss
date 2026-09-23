# Overlap matrix

Baseline: `origin/main` `582d95161cf8220fb37f5224e21e57dcc5c3121c`.

Donors compared from GitHub, not from the dirty worktree:

- PR #107 routed engine (open, not draft): https://github.com/DataBossX/DataBoss/pull/107
- PR #110 source-bound finish (open, draft): https://github.com/DataBossX/DataBoss/pull/110
- PR #114 trusted kernel (open, draft): https://github.com/DataBossX/DataBoss/pull/114
- PR #116 challenger notes (open, draft): https://github.com/DataBossX/DataBoss/pull/116
- Issues #68 and #69, whose named donors #51 #52 #54 #61 #66 #67 are closed, unmerged, and titled parked / do-not-merge
- Issue #94 defects, checked on main and addressed in PR #114's file list

Disposition column uses the three words requested: `keep`, `port`, `reject`.

- `keep` — already on main and should stay the canonical implementation
- `port` — behavior is worth a bounded slice onto main, after review, without merging the donor wholesale
- `reject` — do not merge this implementation into the runtime

Issue #69's finer labels, when they add information: `CANONICAL`, `PORT_AS_BOUNDED_SLICE`, `PRESERVE_AS_TEST_OR_REFERENCE`, `QUARANTINE`, `SUPERSEDE_AFTER_PROOF`.

Code bodies of parked PRs were not re-read. Paths, sizes, and titles were. Where behavior is inferred only from a path name, the cell says so.

## Hard collisions (read this before any port)

Three open or local lines want to be "the next migration" and they do not share a filename:

| Line | Migration file | Tables (from the SQL text) |
| --- | --- | --- |
| PR #107 | `migrations/002_engine_tables.sql` | `model_route_decisions`, `derived_cache`, `engine_receipts`, `candidate_comparisons` |
| PR #114 | `migrations/002_kernel_and_connectors.sql` | `task_manifests`, `connector_cursors`, `evidence_spans`, `claims`, `claim_support`, `conflicts`, `review_gates`, `review_decisions` |
| Local commit `3149ead` (not main) | `migrations/002_governor.sql` | `improvement_proposals`, `task_envelopes`, `writer_leases`, `cycle_receipts`, `learning_records`, `tournament_rounds` |

Main's `initialize()` loads only `001_initial_schema.sql` by path, so none of these run on main today. PR #107 and PR #114 both edit `src/databossx/database.py`. The local commit changes `initialize()` to execute every `migrations/*.sql` in sorted order. If that glob lands, all three `002_*` files apply together with no schema-version row. That is a silent merge, not a reviewed kernel.

Textual conflicts, same path edited by more than one donor against main:

| Path | Who edits it |
| --- | --- |
| `src/databossx/__init__.py` | #107, #114, and parked #51 #61 #67 (adds a package) |
| `src/databossx/database.py` | #107, #114, local `3149ead` |
| `src/databossx/hashing.py` | #107 (+46/−17), #114 (+6/−0) |
| `src/databossx/intake.py` | #107 |
| `src/databossx/orchestrator.py` | #107; parked #61 also replaces orchestrator behavior (path overlap) |
| `horizon/controlled_loop.py` | #107 |
| `grocery_report_pipeline.py`, `horizon/repair.py`, `backend/server.py` | #114 and local `3149ead` |
| `backend/server.py`, `frontend/src/App.js` | parked #54, plus #114 on the backend |
| `tests/conftest.py` | #110 (+4/−4) |
| `src/databossx/cli.py`, `src/databossx/__main__.py` | #114 adds them; parked #51 and #67 also add a CLI / main |

PR #116 shares no paths with #107, #110, or #114.

## Matrix

| Capability | Main status (`582d951`) | Donor PR | Collide-risk | Keep / port / reject |
| --- | --- | --- | --- | --- |
| Canonical package `src/databossx` | Present. Eight modules. PR #50 merged. Flat layout, not the build-plan tree. | #50 keep. #114 and #107 extend it. | High if a parked package (`command_brain/`, `products/title/`, `db.py` vs `database.py`) is merged beside it. | keep (`CANONICAL`) |
| Migration `001` and per-project SQLite | Present. One script. WAL and foreign keys set in `connect()`. No schema-version table. | #50. Parked #51 ships a different `migrations/001_kernel.sql` plus `002`–`009`. | High. Two files both claiming to be migration 001. | keep main `001`. reject #51's migration chain as a second root (`QUARANTINE`) |
| Content-addressed vault copy | Present. `copy_file_to_vault` writes `vault/sha256/<2>/<hash>` via temp file and `os.replace`. Skips if destination exists. Source is not deleted. | #107 reworks hashing (larger diff). #114 touches hashing lightly. | Medium. Same function, two patches. | keep the main contract. port #107 single-pass hash-while-copy only if tests show the bytes match (`PORT_AS_BOUNDED_SLICE`) |
| Project intake, snapshot, duplicate link | Present. `create_project`, `register_source_connection`, `inventory_source`, template registration. | #107 small intake diff. | Low on behavior, medium on the file. | keep |
| Seeded intake tasks | Present. Three tasks inserted as `READY`. No dependency rows. No lease. | #107 orchestrator diff. #114 `tasks.py` adds transitions and leases. | Medium. Two task engines. | keep the seed. port one state machine (prefer #114's explicit transitions) and do not also take #107's claim path until they share that machine |
| Control API | Present and thin: `GET /healthz`, `GET /projects/{id}`, `GET /projects/{id}/assets`. FastAPI optional. No bind inside `create_app`. | #114 adds tasks, audit search, claims, and a drive-scan route (`api.py` grows to about 131 lines). | Medium with any second API (parked #54 `landman_api.py`, #67 `command_brain/api.py`, legacy `backend/server.py`). | keep the factory. port #114's read routes after auth review. reject a second server |
| Audit table + FTS5 | Present. `audit()` inserts rows. FTS trigger on insert. No search route. | #114 exposes audit query. | Low. | keep table. port the read API with #114 |
| Outbox table | Present, unused by Python. | None of #107/#110/#114/#116 add a publisher. Parked #66 describes audit/outbox in the issue text; code not re-read. | Low until a second outbox is introduced. | keep the table. port a publisher later as one implementation. reject a second outbox |
| Approvals table | Present. Columns are project, artifact hash, approver, expiry, payload JSON. No writer binds an envelope hash. No single-use enforcement in code. | #68 requires single-use hash-bound approval. #114 policy engine has expiring external-write approval (from `policy.py` symbols). Parked #66 has `APPROVAL_SCHEMA.json`. | High if both approval stores land. | keep the table as the only store. port one binder. reject a second approval system |
| Task lease rows | Table present. No Python lease/heartbeat/expiry. | #114 `lease_task`, `heartbeat`, `expire_stale_leases`. #107 `claim_ready_tasks` takes an exclusive SQLite lock and leases a batch. Local `002_governor.sql` adds `writer_leases` with a fence. | High. Three lease designs. | port exactly one lease implementation onto `task_leases`. reject extra lease tables until that one is proven |
| Policy engine | Absent. No `policy.py`. Deterministic-vs-LLM split is not enforced in code. | #114 `PolicyEngine` (confidentiality, connector scan, vault ingest, external write, conflict hold). #107 `routing.py` also filters `local_only` and blocks LLM routes for hash, inventory, title math, chain rules, compare, receipts. | High. Two policy engines. | port one policy module. Fold #107's hard filters into it. reject a second engine (`command_brain/policy.py` included) |
| Model route decisions | Absent. Build-plan entity `ModelRouteDecision` has no table. | #107 `route()`, `model_route_decisions` table, considered-and-rejected list. | Medium with #114 policy and with parked #67 `model_gateway.py`. | port #107 router as the Phase 4 slice, behind the one policy engine. reject hardcoded provider winners |
| Candidate comparison that preserves conflicts | Absent on main. Grocery reconciliation can flag decimal sums; it is not a field-level candidate graph. Agreement-is-not-evidence is documented in the blueprint only. | #107 `compare_candidates`: unsupported without source hash, `CONFLICT` when evidenced values differ, no automatic winner. | Low with #114's `conflicts` table if the comparison writes into that table. High if it grows its own `candidate_comparisons` store forever. | port the comparator. persist into #114's `conflicts` / claims model rather than a permanent second store (`SUPERSEDE_AFTER_PROOF` for `candidate_comparisons` if claims exist) |
| Derived-work cache | Absent. | #107 `DerivedWorkCache` keyed by recipe version + input hashes + params. Table `derived_cache`. | Low. | port |
| Sealed receipts | Absent. Horizon controlled-loop receipts are unsigned JSON on main (the #107 PR body states failure receipts also omit input hashes; that claim matches the files #107 changes: `horizon/controlled_loop.py`, new `horizon/receipts.py`). | #107 `seal_receipt` / `verify_receipt` over canonical JSON. Local governor has `cycle_receipts` without a documented seal in the SQL alone. | Medium. Two receipt tables. | port #107 sealing. reject an unsealed second receipt log as authority |
| Exclusive batch claim | Absent. | #107 `claim_ready_tasks`. | High with #114 `lease_task` (see lease row). | port the exclusive lock behavior into the single leaser. reject a parallel claimer |
| Evidence span, claim, support, conflict | Absent as tables. Grocery facts carry path and snippet in CSV, not a span row. | #114 `evidence.py` plus `002_kernel_and_connectors.sql`. | Medium with #107 comparison table (duplicate conflict stores). | port #114 graph as the canonical evidence model |
| Review gate and review decision | Absent. | #114 tables and, in policy, `require_human_for_conflicts`. | Low if it is the only review store. | port |
| Task manifests and idempotency | Absent. Tasks have `payload_json` only. | #114 `task_manifests`. #68 asks for `TaskEnvelope.v2` (base, allowlists, budgets, rollback). Parked #66 and #67 ship envelope schemas / `command_brain/envelope.py`. | High. Envelope vs manifest vs payload_json. | port one hashable envelope onto the existing `tasks` row. reject a second task table as the system of record |
| Local connector interface | Partial. Intake walks a directory with a skip set. No dry-run flag, no cursor, no `Connector` protocol. | #114 `connectors/local.py` (`scan(dry_run, cursor)`). | Low. | port |
| Read-only Drive connector and vault sync plan | Absent. | #114 `connectors/drive.py`, `sync.py`. Default local mirror or injected list API. `DriveWriteRefused`. This PR text says it is not the Section 7 pipeline in #97. | High with #97 (open, not draft, Drive sync in the title) and with any client Drive IDs. #114's public diff must be re-reviewed for IDs before port; this census did not find client IDs in the symbol list, which is not a proof of the whole diff. | port the read-only planner only. reject #97 as a second Drive writer. reject any write/delete/share without an expiring hash-bound approval |
| Horizon exact interest math | Present. `horizon/interest.py` uses `fractions.Fraction`. `parse_interest`, `sum_interests`, `net_acres`. | #114 `titlemath.py` is a thin adapter (`conservation_holds`, import helper). | Low if it imports Horizon. High if a second fraction library arrives (parked #51 `economics.py` / `ledger.py`, not re-read). | keep Horizon math. port the adapter. reject a second arithmetic implementation |
| Instrument chaining and workbook validation | Present in `horizon/chaining.py`, `validation.py`, `workbook_qa.py`, `versioning.py`. | No equivalent new package in #107/#114. | Low. | keep |
| Workbook repair | Present and unsafe relative to Issue #94. `horizon/repair.py` parses with `recover=True` and removes an errored formula (`t="e"`), including the cached error marker. Lines at `582d951`: parser at line 55, removal note at line 71. | #114 edits `horizon/repair.py` (+114/−31) and adds `tests/test_issue94_integrity.py`. Local `3149ead` edits the same file. | High. Two patches of the same function. | port one fail-closed repair. reject merging both patches. keep the rest of Horizon |
| Grocery stages A–I | Present in one file, `grocery_report_pipeline.py` (1773 lines at `582d951`). Inventory through dashboard. | Build plan says split into workers. #114 patches extraction defects. #110 is a different finish toolkit, not a rewrite of A–I. | Medium on the extraction functions. | keep the pipeline as the current worker until it is split. port #114's defect fixes. reject a second report writer |
| Recording-date fabrication | Defect on main. If no recorded/filed label matched, line 904 calls `parse_date(text)` and stores it as `recording_date` at confidence 0.4. | #114 grocery diff (+83/−15). Issue #94 test 3. | High with the local grocery edit. | port the fail-closed behavior from one reviewed patch |
| Decimal interest parser | Defect on main. `_DECIMAL_RX` at line 823 requires 4–9 digits after the point (`0?\.\d{4,9}`), so `0.5`, `0.25`, and `0.125` do not match. Sums use those captures. | #114 grocery diff. Issue #94 test 4. | High with the local grocery edit. | port |
| Legacy backend authentication | Defect on main. Data routes have no auth dependency: upload, documents, logs, analytics. Health is `GET /api/health`. | #114 `backend/security_controls.py` and a rewritten `server.py` (+188/−319). | High with parked #54, which also edits `backend/server.py`, and with the local rewrite. | port #114's fail-closed controls. reject #54's landman API as a second backend |
| Credentialed wildcard CORS and bind | Defect on main. `allow_origins=["*"]` with `allow_credentials=True` (lines 42–43). `uvicorn.run(..., host="0.0.0.0", port=8001)` at line 500. | #114 server rewrite. | Same file as above. | port loopback bind and an explicit origin allowlist |
| Mock OCR | Defect on main. `process_ocr` returns a high-confidence synthetic legal-looking paragraph (`confidence_score` 0.95, engine `demo_ocr`). | #114 claims real-upload mode refuses mock OCR. | Same file. | port a refusal for any non-synthetic mode. reject mock text as evidence |
| Original-file moves | Present and contrary to the blueprint's immutable-originals rule. Grocery `apply_quarantine` calls `shutil.move` (line 725) when that flag is passed. Horizon `foundation._quarantine` moves duplicates (line 202); `run_cleanup` on the path inspected calls `dedupe(..., move=False)`, so the default cleanup path reports rather than moves. The move function still exists. | Blueprint retire list: automatic original-file moves. Neither #107 nor #114 removes the move API. | Low between donors. High against the rule if a caller passes the flag. | reject move/delete/rename of originals. keep plan-only duplicate reports |
| Source-bound finish toolkit | Absent. | #110 package: PDF page census, page ledger, identity union, purity and format checks, date-role split, ZIP CRC and SHA-256, five-dimension tournament, access probe. Tests claimed by the PR body: 18 passed on synthetic fixtures. Not re-run here. | Low, except `tests/conftest.py` (+4/−4). A second `hashing.py` lives inside the package, not in `src/databossx/`. | port as a separate tool (`PORT_AS_BOUNDED_SLICE`). reject importing it as the kernel. preserve its tournament as a reference, not a second judge |
| Date-role isolation (preparation is not recording, filing is not approval) | Absent as a shared function. Grocery currently collapses unlabeled dates into `recording_date` (row above). | #110 `dates.py`. #114 grocery patch for the recording-date defect. | Medium if both patches define date roles differently. | port one date-role function and use it from grocery |
| Challenger tournament writeup | Absent on main. | #116, four markdown files, zero code. PR text says do not merge the folder as runtime and points at #107 then #114. | None on paths. High if someone treats the prose as a merge instruction. | reject as runtime (`PRESERVE_AS_TEST_OR_REFERENCE`) |
| Publication-policy scanner | Docs only on main (`DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md`). No gate script. | Open draft #32 adds a gate (not diffed here). #114 adds `tests/test_publication_policy.py`. Local `7440ee3` adds a scanner under an `_AI_*` folder. | Medium. Two scanners. | port one gate onto main after review. reject tournament-folder copies as the gate |
| Issue #94 regression suite | Absent on main. Repair tests exist (`tests/test_horizon_repair_orchestrator.py`, 5 tests) and do not encode the seven mandatory cases. | #114 `tests/test_issue94_integrity.py` and `tests/test_backend_security.py`. | High with the local copy of the same test module, which was still dirty during this census. | port one suite. reject maintaining two |
| Continuous improvement governor | Absent on main. No proposal, ranker, envelope, fence, or learning record. | Issue #68 specifies the cycle. Issue #69 asks for docs under `docs/continuous_improvement/`, which are absent. Parked #67 is a Command Brain package (51 files, `002_command_brain.sql`). Local `3149ead` adds `src/databossx/governor/` (not on main). | Extreme if #67, #114, #107, and the local governor all merge. | reject merging #67 or the local package as the kernel. port a single synthetic cycle onto the one database after the overlap review (`PORT_AS_BOUNDED_SLICE`) |
| Writer lease and monotonic fence | Absent in code. `task_leases` has worker id and expiry, no fence column. | Issue #68 item 4. Parked #66 (Postgres lease, per issue text; `WRITER_LEASE_SCHEMA.json` is in the file list). Local `writer_leases.fence`. | High. SQLite vs Postgres, and a second table. | port fencing into the one SQLite lease. reject Postgres as a second database (blueprint decision is SQLite until measured need) |
| Frozen-baseline tournament and judge | Absent as a blocking gate. Horizon QA scores workbooks; that is not an improvement tournament. | #107 does not add a judge. #110 `tournament.py`. #116 describes a tournament. Parked #67 `judge.py` and `tournament.py`. Local `governor/tournament.py`. | High. Four judges. | reject every extra judge as runtime. port one blocking judge later, under Issue #68 phase 3, not in the first slice |
| Learning memory | Absent. Audit rows are not reviewed learning records. | Issue #68 item 9. Parked #67 `memory.py`. Local `learning_records` table. | High. | reject raw model claims as knowledge. port a reviewed record type only after the envelope exists |
| Command Center / second UI | Main already has four UIs plus two APIs (see census). | Parked #66 adds `apps/control-center-web/` (64 files, +11760). Open #100 is a Control Tower kernel (draft, 75 files). #116 text says #100 should not become the OS. | High. | reject new control-plane apps. keep one future Vite UI (`mineral_deal_room` patterns only). `QUARANTINE` #66 and #100 as donors |
| Durable executor / workers | Absent. No worker process. | Parked #61: `executor.py`, `workers.py`, intake idempotency tests (12 files). Overlaps `__init__.py`, `database.py`, `intake.py`, `orchestrator.py`. | High on those four files. | port idempotent transition and crash-recovery tests onto main's tables. reject merging #61 as a second orchestrator |
| Title economics and second title product | Horizon math is the title arithmetic on main. No `products/title`. | Parked #51: `products/title/` plus nine migrations. | High. Replaces the migration root. | reject the merge (`QUARANTINE`). preserve economic ideas as reference until field-level evidence exists |
| Unified report pipeline | Grocery + Horizon already overlap each other (two inventories, two hashes, two audits). | Parked #52: another `src/databossx` CLI, abstract, excel/pdf report, dashboard (50 files). | High. Third report writer. | reject (`QUARANTINE` per the blueprint note on PR #25's class of duplicate) |
| Landman document API | DOTO and grocery extract text. No shared title-intelligence module. | Parked #54: `title_intelligence.py`, `backend/landman_api.py`, edits `backend/server.py` and `frontend/src/App.js`. | High on `backend/server.py` with #114. | reject the merge. port tested parsers only after the mock-OCR path is dead |
| Security baseline proof | `SECURITY.md` and secret-scan workflow exist. Issue #2 is still open. Issue #72's four docs are absent. Branch protection, push protection, CodeQL, and Dependabot status were not queried. | #114 adds only `docs/security/REPOSITORY_SECURITY_BASELINE.md` (one of the four files). | Low on code, high on process. | keep the scan workflow. port the missing docs only when they record real settings. reject treating a stub as `REPOSITORY_SECURITY_BASELINE_PROVEN` |
| Issue #93 publication hold | Open. Many client-shaped draft PRs remain open (titles in the census: sections, abstracts, Penterra, Section 7, Section 32). This census did not open their diffs. | Hold applies to #95, #97, #101, #103, #104 and neighbors until an owner classifies them. | Process collide with any kernel merge that rides along in a dirty branch. | reject merging those PRs as runtime. classification itself is owner work, not this folder |
| This inventory folder | Not on main. | This run. | None if it stays unimported. | reject as runtime |

## What "port" does not mean

A `port` cell is not permission to merge the donor branch. Issue #69 forbids merging entire donor PRs, forbids a second queue or policy engine, and forbids auto-merge. Issue #94 forbids fixing main by merging the old read-only review PR, and it forbids client mutation. Issue #93 forbids merging client-shaped lineages while the hold is open.

The only open donors whose code is in the right shape for a later bounded port are #107 (engine behaviors) and #114 (evidence graph, leases, policy, Issue #94 fails, read-only connector), and they collide on `database.py`, `hashing.py`, `__init__.py`, and the `002` migration number. They have to be sequenced by a human reviewer onto one `002`. #110 can follow as a side tool. #116 should not be sequenced at all.

Parked #51, #52, #54, #61, #66, and #67 stay closed. Their useful contracts (envelope schema, fencing, idempotent recovery tests) can be re-implemented against main's `001` tables. Reopening them as merge candidates recreates the fragmentation Issue #68 describes.
