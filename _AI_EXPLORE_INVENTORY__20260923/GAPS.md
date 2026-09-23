# Gaps on main for Phase 2 and the Issue #68 first slice

Baseline: `origin/main` `582d95161cf8220fb37f5224e21e57dcc5c3121c`.

Phase 2 in the blueprint and build plan is the trusted kernel. It is defined to depend on Phase 1 (a real, hash-approved title candidate). Phase 1's named vehicle, PR #26, is closed unmerged and parked. This file does not treat that gate as passed. It lists what the kernel code on main still lacks even as a software slice.

Issue #68's first executable slice is a synthetic-only improvement cycle. Issue #69 is the inventory-plus-one-cycle version of that slice and names output paths under `docs/continuous_improvement/`. Those paths are absent on main. This folder is not those paths and does not complete Issue #69.

## Phase 2 deliverables

Build-plan id `P2`, name `trusted_kernel`. Gate text: crash recovery is idempotent, originals cannot be mutated, and released artifacts are reconstructable.

| Deliverable | On main | Evidence | Gap |
| --- | --- | --- | --- |
| Canonical package | Partial | `src/databossx/` eight modules, version `0.1.0`, from PR #50 | Planned packages `control`, `domain`, `vault`, `connectors`, `memory`, `routing`, `workers`, `products/*` are absent. No `pyproject.toml`. |
| Numbered migrations | Partial | Only `migrations/001_initial_schema.sql`. `initialize()` reads that path and does not record a version | No `002`. No migration ledger. Applying any donor `002_*.sql` is undefined. Three competing `002` drafts exist off main (see overlap matrix). |
| Append-only vault | Partial | `copy_file_to_vault` copies to a content-addressed path and does not delete the source | No read-back hash check. No API that refuses overwrite, symlink escape, or path traversal. Grocery and Horizon still contain `shutil.move` quarantine helpers. |
| Event ledger | Partial | `audit_events` plus FTS, and an unused `outbox_events` table | Nothing publishes the outbox. Audit payloads are free JSON, not a hash chain. No reconstruction function from events to an artifact. |
| Task graph | Partial | Tables for runs, tasks, dependencies, attempts, leases. Seed inserts three `READY` tasks and does not insert dependencies or leases | Blueprint states (`PLANNED`, `BLOCKED`, `LEASED`, `RUNNING`, `WAITING_HUMAN`, `SUCCEEDED`, `FAILED_*`) are not enforced. No idempotency key, heartbeat, stale-lease recovery, or single writer. |
| Policy engine | Absent | No module and no `config/policies/` | Confidentiality, egress, external-write approval, and "deterministic work never routes to an LLM" are prose in the blueprint only. |
| Local connector | Partial | Intake walks one directory | No connector protocol, dry-run, cursor, or least-privilege scope test. |
| Evidence and review API | Absent | Control API has three GET routes and no claims, conflicts, or review routes | 31 blueprint entities have no table (census). Examiner review UI is sample data in `mineral_deal_room`. |

### Gate checks that main cannot pass

| Gate condition | Status on main |
| --- | --- |
| Crash or restart is idempotent | Not implemented. No resume test in `tests/test_databossx_foundation.py` (3 tests). |
| Originals cannot be mutated through any API | Not true of the whole tree. The foundation copy path does not mutate sources. `grocery_report_pipeline.apply_quarantine` moves files when invoked. `horizon.foundation._quarantine` moves files when invoked. Legacy `backend` upload stores caller bytes and returns mock OCR. |
| Audit log reconstructs every artifact | Not implemented. Audit insert exists. Replay does not. |
| Source change after inventory blocks downstream approval | Not implemented. Approvals are a table with no writer. |
| Material conflicts stay conflicts | Not implemented in the kernel. Grocery can still store an unlabeled date as `recording_date`. |
| Loopback by default | Canonical `create_app` does not bind. Legacy server binds `0.0.0.0`. |

Phase 2 also says to migrate PR #26 checkpoints and Grocery stages into typed tasks. PR #26 is not on main. Grocery stages are still one script, not task types. That migration has not started.

## Issue #94 defects still on main

Issue #94 is open. Each item below was read from `git show 582d951:<file>`.

| # | Defect | Where |
| --- | --- | --- |
| 1 | Errored Excel formulas can be stripped and the cached error cleared | `horizon/repair.py` XML parser `recover=True` (line 55); errored formula removed (line 71) |
| 2 | Malformed worksheet XML is recovered rather than refused | same parser |
| 3 | Unlabeled dates become `recording_date` | `grocery_report_pipeline.py` lines 903–904, confidence 0.4 |
| 4 | Ordinary decimals `0.5`, `0.25`, `0.125` miss the regex | `_DECIMAL_RX` line 823, `\d{4,9}` |
| 5 | Data endpoints have no auth dependency | `backend/server.py` upload, documents, logs, analytics |
| 6 | Wildcard origins with credentials, bind all interfaces | lines 42–43 and line 500 (`0.0.0.0`) |
| 7 | Mock OCR emits legal-looking text at confidence 0.95 | `process_ocr` |

The seven mandatory regression tests named in the issue are not in `tests/` on this commit.

PR #114 is the open draft that claims to add those regressions and a kernel slice. A local commit `3149ead` on `cursor/kernel-governor-tournament-7f1f` also touches the same defect files and is not main. Neither has closed the GitHub issue. Port one reviewed patch. Do not treat either branch tip as the fix until the seven tests pass on a clean tree and an independent review says so.

## Issue #68 first slice

The issue's first executable slice is ten steps. Main has none of the machinery those steps call.

| Step | On main |
| --- | --- |
| 1. Detect a missing or weak regression | No governor detector. The weak tests are visible to a human (Issue #94, three foundation tests) but nothing records that detection as data. |
| 2. Immutable proposal and ranked decision | No `ImprovementProposal` type, table, or ranker. No value, risk, cost, reversibility, confidence, or hard veto fields. |
| 3. Hashable TaskEnvelope | Tasks store `payload_json` only. No envelope hash, base commit, allowlist, budget, canary, or rollback field. |
| 4. L2 isolated lease and single-use approval | Lease table is unused. Approvals are not bound to an envelope hash and are not single-use. No fence. |
| 5. Sandbox branch or worktree only | Not a code path. Git operations are outside the package. |
| 6. Smallest test and fix | Not a code path. |
| 7. Invariant, golden, adversarial, rollback suites | `tests/unit`, `tests/golden`, `tests/adversarial` do not exist. No rollback rehearsal. |
| 8. Independent judge | No judge module. |
| 9. Draft PR only if blocking gates pass | Not a code path. Auto-merge is not authorized by the issue in any case. |
| 10. Terminal receipt and reviewed LearningRecord | No receipt sealer and no learning-record store in the canonical package. |

Blocking gates from the same issue (unknown writer, stale lease, changed baseline hash, active release hold, secret exposure, unreproducible evaluation, failed rollback, missing receipt) are not executable checks.

Issue #68 also asks for a Phase 0 overlap matrix of parked PRs #51, #52, #54, #61, #66, and #67. Those PRs are closed and parked. This packet's matrix covers them at title-and-path level and covers the live kernel donors #107 and #114 at symbol level. That does not satisfy Issue #69's required files:

- `docs/continuous_improvement/CANONICAL_OVERLAP_MATRIX.md`
- `docs/continuous_improvement/CANONICAL_COMPONENT_MAP.json`
- `docs/continuous_improvement/FIRST_CYCLE_TASK_ENVELOPE.json`
- `docs/continuous_improvement/PHASE0_RECEIPT.md`

Those four files are absent on main. Copying this folder into `docs/` would still miss the JSON component map, the hashable envelope, and a reviewed learning record.

### First slice, sequenced against the real gaps

If a later writer builds the slice on main, the order that avoids a second kernel is:

1. Keep `001` and add a schema-version row before any `002`.
2. Land one `002` that can hold claims, conflicts, leases-with-fence, proposals, and envelopes. Do not land three `002` files.
3. One policy module and one lease function. Fold #107's "no LLM for hash/inventory/title math" rule into that policy.
4. One sealed receipt function. Use it for the cycle receipt.
5. The first synthetic cycle should target an Issue #94 regression that main lacks (decimal parse or unlabeled recording date are the smallest), on synthetic fixtures only.
6. Stop on the Issue #68 blocking gates. In particular, a dirty shared worktree and a second writer (observed during this census) is a stop, not a prompt to continue.

This census does not implement that cycle.

## Issue #72 and #93, which block a kernel merge even after code exists

| Required before a consolidation merge | On main |
| --- | --- |
| Issue #2 credential incident closed with rotation proof | Issue #2 is open. This census did not inspect secrets and did not copy any. |
| Branch protection, required review, required checks, push protection, CodeQL, Dependabot | UNKNOWN. Not stored in git. Missing docs are not evidence the settings are off, and they are not evidence they are on. |
| The four security docs named in Issue #72 | Absent. |
| Issue #93: no open public PR with client/report production authority | False. 24 PRs are open, including non-draft report and Drive PRs #95, #97, #101, #103. Contents were not classified here. |
| One control plane | False as a goal state. Main already runs grocery, Horizon, DOTO, CRA frontend, Vite deal room, Astro website, and a mock FastAPI backend. |

Issue #28's canonical system map and the client evidence manifest are also absent. This file does not restate legal descriptions or party chains from that issue.

## What is already strong enough to build on

These are not gaps. They are the base a kernel port should call instead of rewriting:

- Immutable intake and vault copy (`src/databossx/hashing.py`, `intake.py`)
- SQLite WAL, foreign keys, and the `001` table set
- Horizon `Fraction` interest math and chain reconciliation
- Workbook QA and versioned report outputs
- Grocery stages A–I as the typed-worker backlog, after the two extraction defects are fixed
- Secret-scan workflow with `contents: read`
- Publication policy prose in `docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md`

## Explicit non-goals of this gap list

- Not a claim that Phase 1's real candidate report exists. It does not exist in this public tree, and `PROJECT_STATUS.md` says the real source corpus is not in the checkout.
- Not a ranking of model vendors, and not a Drive census. PR #116 records Drive access as unavailable in that run. This run did not call Drive.
- Not authorization to merge #107, #110, #114, or #116.
