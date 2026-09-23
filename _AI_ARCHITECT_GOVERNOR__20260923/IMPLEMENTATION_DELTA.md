# Implementation delta for the parent writer

Design only. This lists exactly what the single authorized writer should
create or modify, in order. The base is branch
`cursor/kernel-governor-tournament-7f1f` at `5fc0d6c`, which already has
governor v0. Each phase is its own human-reviewed commit or draft PR. The
governor never builds or modifies itself (V6), so every item here is human
work.

## 0. Prerequisites (human decisions and a verbatim kernel slice)

| # | Item | Why | Verified |
| --- | --- | --- | --- |
| 0.1 | **Owner picks one Issue #94 line**: this branch (`3149ead`, `5fc0d6c`) or PR #114 (`e8b9225`) | Two implementations of the same seven regressions exist. The governor vetoes porting one onto the other (P-E, V4). `FIRST_CYCLE.md` uses this branch; its appendix A covers PR #114 | Both lines' suites pass on their own trees |
| 0.2 | **Tracked migration runner.** Replace `src/databossx/database.py` with PR #114's file at `e8b9225`, byte-identical (adds `apply_migrations` and `schema_migrations`; same public API plus one method) | The branch's `initialize()` re-executes every `.sql` file on each call. PR #114's `002` runs `ALTER TABLE tasks`, so it crashes on the second call with `duplicate column name: input_manifest_hash` | Crash reproduced; with PR #114's runner, a double `initialize()` applies `001`, `002_governor`, and `002_kernel_and_connectors` exactly once |
| 0.3 | **Kernel slice, byte-identical from `e8b9225`:** `src/databossx/tasks.py`, `src/databossx/policy.py`, `migrations/002_kernel_and_connectors.sql` (whole file, including its connector and claim tables, so both branches hold identical bytes and a later merge of PR #114 is conflict-free for these paths). One commit, message naming PR #114 and `e8b9225` | The governor needs `tasks.transition`, `PolicyEngine`, and `review_gates`/`review_decisions`, and must not grow its own copies | With 0.2, 0.3, and the section 1.1 migration, the branch suite is 173 passed, 2 failed (the two v0 tests rewritten in 1.4) |
| 0.4 | **Policy fix (separate commit, also reported on PR #114; not pushed there by the governor).** In `src/databossx/policy.py`, add `GOVERNOR_SANDBOX_CAPABILITIES = {"sandbox.worktree.create", "sandbox.fs.write", "sandbox.git.commit", "sandbox.test.run"}` and `KNOWN_CAPABILITIES = LOCAL_ONLY_CAPABILITIES \| GOVERNOR_SANDBOX_CAPABILITIES \| {"connector.scan"}`. Before the final `_allow`, return `_deny("unknown capability", "unknown_capability", considered=considered)` when `capability not in KNOWN_CAPABILITIES` | At `e8b9225`, `decide("totally.unknown.capability")`, `decide("workbook.write")`, and `decide("governor.self_edit")` all return `allowed=True` | After the fix those three are denied; `sandbox.test.run`, `connector.scan`, `vault.copy`, `inventory.hash`, and `allow_connector_scan("google_drive", "read_only")` stay allowed. PR #114's suite: 177 passed before and after (31-line diff) |
| 0.5 | **Close the `_AI_*` publication hole.** In `src/databossx/governor/policy_gate.py`, `_allowlisted` must no longer skip `_AI_*` paths for the `credential` and `private_key` kinds. Only `private_windows_path` may stay allowlisted there | Today any leak inside a packet folder passes `test_current_repo_gate_documents_status` | Code read (`policy_gate.py:40`) |
| 0.6 | Delete any local `runtime/projects/governor/project.db` created by v0 | The revised tables are `CREATE TABLE IF NOT EXISTS`; an old file keeps v0 columns silently. `runtime/` is gitignored, so nothing is lost | n/a |

Until 0.2 to 0.4 land, the governor may run only L0 and L1 (observe,
propose, rank, seal). `G_KERNEL_PRESENT` blocks AUTHORIZE.

## 1. Changes to existing files

### 1.1 Migration

| Path | Change |
| --- | --- |
| `migrations/002_governor.sql` | Replace the whole file with the SQL block in `ARCHITECTURE.md` section 6.1 (SHA-256 `a49ccd173e6b8cf99296897f9cc06975bae5783af0c588feacd0f528f7818567`, 397 lines). Same file name, same six v0 table names, six new `governor_*` tables, 45 objects, no `ALTER TABLE` |

### 1.2 Governor v0 modules (revise in place; keep public names where they exist)

| Path | Change |
| --- | --- |
| `src/databossx/governor/models.py` | Scores become `int` 1 to 5 (`value`, `risk`, `cost`, `reversibility`, `confidence`); add `scope`, `proposal_class`, `proposal_key`, `proposal_hash`. Add frozen `RankDecision`, `Evaluation`, `BenchmarkCase`, `ReviewOutcome`, `LearningRecord`, `VetoResult(id, stage, result, path, line)`. Add `TERMINAL_STATES` (the five names in `ARCHITECTURE.md` 7.1) and `VETO_IDS` mapping V1 to V6 onto the existing `HARD_VETOES` strings. Every record gets `to_json()` and a `content_hash` property |
| `src/databossx/governor/envelope.py` | Remove `DEFAULT_ALLOWLIST`; the write allowlist is exact files supplied by the proposal and validated against V6 protected paths. Build the full `TASK_ENVELOPE.md` section 1 object; `envelope_id = envelope_hash[:16]`; add `validate(env, limits) -> list[str]`, `seal(store, env) -> str`, `verify_inputs(worktree, env)` raising `EnvelopeDrift`. `ALLOWED_AUTONOMY` becomes `{"L0","L1","L2","L3"}`, with L3 requiring the canary purpose |
| `src/databossx/governor/lease.py` | `acquire_lease(db, scope, worker_id, ttl_seconds) -> int` runs in `BEGIN IMMEDIATE`: reads `MAX(fence)`, inserts `fence + 1` with `Z`-format `expires_at`; the SQL triggers refuse a second live holder or a halted scope, surfaced as `StaleWriter`. Add `heartbeat`, `release`, `halt`, `resume`. `assert_lease` compares `Z` strings and also requires `released_at IS NULL` |
| `src/databossx/governor/ranker.py` | `RANKER_VERSION = "next-best-move/1"`; `rank(proposals, veto_map) -> RankDecision` using `fractions.Fraction(value*confidence*reversibility, risk*cost)`, tie-break risk ascending then `proposal_hash` ascending. Keep `rank_proposals` as a thin wrapper for existing callers |
| `src/databossx/governor/cycle.py` | Add `GovernorCycle` with `open(scope, base_commit, open_pr_snapshot) -> str` and `tick(scope) -> str` (one stage per call). Remove `INSERT OR REPLACE`, `_missing_regressions`, `ISSUE94_SEEDS` float scores, and `CYCLE_BLOCKED_MISSING_REGRESSIONS`. Keep `run_synthetic_cycle` as a demo that drives `GovernorCycle` through L0 and L1 only and returns a NOOP or BLOCKED receipt when the kernel slice is absent |
| `src/databossx/governor/policy_gate.py` | Prerequisite 0.5. Export `FORBIDDEN` for reuse by `vetoes.py` |
| `src/databossx/governor/__init__.py` | `GOVERNOR_VERSION = "0.2.0"`, `GOVERNOR_PROJECT_ID = "governor"`; re-export `GovernorCycle`, `canonical_json`, `content_hash` |
| `src/databossx/cli.py` | Keep `census`, `policy-gate`, `tournament`, `cycle`. Add a `governor` subcommand group via `databossx.governor.cli_commands.register(sub)`: `init`, `open`, `tick`, `status`, `approve`, `review`, `halt`, `resume`, `verify-receipts`, `learning-review`, `benchmarks activate`. If PR #114's `cli.py` is also adopted, merge its `health`, `project-create`, `drive-scan`, `drive-sync-plan` into the same parser; there is still only one CLI |
| `src/databossx/hashing.py` | Add `store_bytes_in_vault(data: bytes, vault_root) -> StoredAsset` next to `copy_file_to_vault` (temp file, `os.replace`, re-hash check) |
| `docs/CONTINUOUS_IMPROVEMENT_GOVERNOR.md` | Replace the v0 description with a short pointer to the implemented modules and the five terminal states |

### 1.3 Governor defects the governor itself may not fix (V6)

These come from the first cycle's vetoed proposal P-D and from reading v0.
They land as human commits inside the 1.2 changes: the self-inclusive
`DEFAULT_ALLOWLIST`, lease stealing, mutable proposals, float scores, the
`_AI_*` publication allowlist, and the missing approval, audit, and receipt
chain.

### 1.4 Existing tests to rewrite

| Path | Change |
| --- | --- |
| `tests/test_governor.py::test_stale_writer_rejected` | Worker-b's `acquire_lease` while worker-a is live must raise `StaleWriter`. After `release` (or expiry), worker-b gets fence 2, and `assert_lease(..., "worker-a", 1)` raises |
| `tests/test_governor.py::test_synthetic_cycle_and_census` | Assert the demo returns `CYCLE_NOOP_NO_ELIGIBLE_PROPOSAL` or `CYCLE_BLOCKED_REQUIRES_AUTHORITY_OR_BASELINE`, never ACCEPTED, when run without the kernel slice or approvals; keep the census assertions |
| `tests/test_governor.py::test_ranker_vetoes_release_and_prefers_issue94` | Use integer-scored seeds; assert the V3-vetoed release proposal is excluded and the ranking is permutation-invariant |
| `tests/test_governor.py::test_envelope_hash_is_stable` | Also assert `envelope_id == envelope_hash[:16]` and that a write path under `src/databossx/governor/` is rejected |

## 2. Files to create

### 2.1 Configuration (reviewed data, not code)

| Path | Content |
| --- | --- |
| `config/governor/governor.v1.toml` | `schema = "databossx.governor.limits/1"`; `profile = "public-safe"`; `scopes = ["repo:DataBossX/DataBoss"]`; `sandbox_capabilities` = the four in 0.4; `budget_ceiling = {max_files_changed = 5, max_diff_added_lines = 200, max_diff_removed_lines = 100, max_test_invocations = 20, max_wall_seconds = 1800, max_model_calls = 0, max_cost_usd_cents = 0}`; `protected_paths` = the V6 list in `TASK_ENVELOPE.md` section 3; `workbook_suffixes = [".xlsx", ".xlsm", ".xls", ".xltx", ".ods"]`; `synthetic_marker = "SYNTHETIC TEST DOCUMENT -- NOT REAL TITLE DATA"`; `circuit_breaker_consecutive = 3`; `envelope_max_ttl_seconds = 86400` |
| `config/governor/benchmarks/issue94.json` | The six cases in `FIRST_CYCLE.md` section 2, each `{case_key, case_version: 1, suite: "adversarial", target_ref, issue_ref: "DataBossX/DataBoss#94", input_text, expect, pinned_by: []}`. `status` starts `REVIEWED` and becomes `ACTIVE` only through `databossx governor benchmarks activate` |

### 2.2 Modules under `src/databossx/governor/`

Style: `from __future__ import annotations`, frozen dataclasses, every
connection through `DataBossDatabase`, no new third-party dependency.

| File | Public interface | Notes |
| --- | --- | --- |
| `canonical.py` | `canonical_json(obj) -> bytes`; `content_hash(obj) -> str` | Recursive pre-check raises `TypeError` on `float`, `bytes`, `set`, non-`str` keys; uses `hashing.sha256_bytes` |
| `limits.py` | `GovernorLimits.load(repo_root)`; `.capability_allowed(cap) -> PolicyDecision` (governor allowlist **and** kernel `PolicyEngine.decide`); `.ceiling_for(purpose) -> str` | Never trusts a default allow |
| `vetoes.py` | `evaluate_proposal`, `evaluate_envelope`, `evaluate_diff`, `evaluate_texts`, each returning `list[VetoResult]` | Pure; rules exactly as `TASK_ENVELOPE.md` section 3; V5 imports `policy_gate.FORBIDDEN` |
| `benchmarks.py` | `load_cases(path)`, `register(store, cases)`, `active_cases(store)` | Refuses a case whose `input_text` lacks the synthetic marker |
| `probe_harness.py` | `run_text_probe(case_json) -> dict` | Mirrors `tests/test_issue94_integrity.py::_facts_from_text`; prints canonical JSON of `{owner_set_complete, all_decimals, conflicts}` |
| `observe.py` | `run_probes(worktree, cases) -> list[Finding]` | Runs `probe_harness` inside the worktree with the sandbox environment; `pinned_by` checked with `pytest --collect-only -q` |
| `proposals.py` | `compile_findings(findings, base_commit, scope, open_prs) -> list[ImprovementProposal]`; `score(finding) -> dict[str, int]` | Rules in `ARCHITECTURE.md` section 8; `proposal_id = f"{key}-{hash[:12]}"` |
| `authorize.py` | `binding_hash(purpose, envelope_hash, **extra) -> str`; `consume(db, approval_id, purpose, bound_hash, envelope_hash, fence)` | Inserts `governor_approval_uses` (the trigger checks hash, project, expiry); rejects `approver_id` equal to a lease holder or starting with `governor`; never inserts `approvals` |
| `sandbox.py` | `Sandbox.create(repo_root, cycle_key, base_commit)`; `.env()`; `.run(argv, timeout_s)`; `.diff_summary()`; `.patch_bytes()`; `.tree_sha()`; `.revert_paths(paths)`; `.teardown()` | `git worktree add --detach runtime/governor/worktrees/<cycle_key> <sha>`; command allowlist (`git apply, diff, commit, revert, rev-parse, status, write-tree, checkout -- <path>`, `python -m pytest`), anything else raises `SandboxCommandDenied` |
| `builders.py` | `Builder` protocol with `apply_test` and `apply_fix`; `ScriptedPatchBuilder(test_patch, fix_patch)` | Cycle 1 uses the reviewed patches in `FIRST_CYCLE.md` section 5 |
| `evaluate.py` | `run_suite(sb, node_ids, role, suite, fence) -> Evaluation`; `outcome_set_hash(junit_xml) -> str`; `env_manifest() -> dict`; `canary_compare(sb_base, sb_cand, normalize) -> Evaluation` | `pytest -p no:cacheprovider -o addopts= --junitxml=<tmp>`; `command_hash = content_hash(argv)` |
| `review.py` | `open_gate(db, cycle, bundle_artifact_id) -> int`; `record_decision(...)`; `latest_decision(...)` | Kernel `review_gates`/`review_decisions`; rejects the builder or proposer as reviewer |
| `receipts.py` | `build(store, cycle_id)`, `write(config, store, receipt) -> str`, `verify_chain(config, store) -> list[str]` | `receipt_id = receipt_hash[:16]`; `prev_receipt_hash` from the latest row or `GENESIS` |
| `learning.py` | `candidate_from_cycle(store, cycle_id)`; `review(db, record_id, reviewer_id, accept)` | Structured facts only |
| `store.py` | `insert_proposal`, `set_proposal_status`, `open_cycle`, `set_stage`, `close_cycle`, `insert_rank_decision`, `insert_envelope`, `set_envelope_state`, `insert_evaluation`, `insert_receipt`, `insert_learning_record`, `register_benchmark_case`, `get_open_cycle` | Every mutator takes `(conn, scope, worker_id, fence)`, calls `lease.assert_lease` first, and writes `audit_events` in the same transaction |
| `cli_commands.py` | `register(subparsers)` | `approve` prints the bound object, requires typing the first 12 hex characters and `--expires`, and refuses when stdin is not a TTY. That stops an automated caller from approving; it is not authentication, which remains a kernel gap |

### 2.3 New tests (flat `tests/`, synthetic only)

| Path | Proves |
| --- | --- |
| `tests/test_governor_schema.py` | The 67 checks from this packet's verification script (`RECEIPT.md`): zero name collisions with every other migration; idempotent re-apply; coexistence with PR #114's `002` under the tracked runner; every trigger and `CHECK` in `ARCHITECTURE.md` 6.2 |
| `tests/test_governor_canonical.py` | Float, NaN, and `set` rejected; key order irrelevant. **Golden vectors** from `FIRST_CYCLE.md`: envelope `45b4d6606a6efb73b137fbc8ad23fca027684ec166584db1c580fe10689f297f`, P-A `2b455789fe353a5d49d26c3e58a0bd49b7c320c5896fdd11ccf12ee574998631`, empty outcome set `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`. Fixtures live in `tests/fixtures/governor/` |
| `tests/test_governor_ranker.py` | Permutation invariance; vetoed proposals excluded; tie-break order; golden rank hash `120f6aaa12b92d5246f2e0e9033968d95bb421231f0e1d4b7d3a409ac6f084d9` |
| `tests/test_governor_vetoes.py` | One hit and one clear case per veto; secret strings assembled at runtime (`"sk-" + "a" * 24`), never literal |
| `tests/test_governor_lease.py` | Two connections race on `acquire_lease`; the loser gets `StaleWriter`; stale-fence writes rejected; `halt` blocks; expiry yields fence + 1 |
| `tests/test_governor_authorize.py` | Wrong hash, wrong project, no expiry, expired, reused, and self-approval all rejected; the cycle-1 canary binding hash equals `e45d098658839d360516b7145b84c0fb5d2a26a9fbaf782f21bc42f3230a74af` |
| `tests/test_governor_receipts.py` | Chain verifies; a flipped vault byte, a deleted receipt, or a reordered receipt is detected |
| `tests/test_governor_cycle_e2e.py` | In `tmp_path`: `git init` a toy repository with a planted fail-open predicate and one benchmark case; `open` then repeated `tick` with `ScriptedPatchBuilder` and a scripted reviewer reach `CYCLE_ACCEPTED_FOR_INDEPENDENT_REVIEW` with one receipt, one learning candidate, and the worktree removed. Variants: red baseline gives BLOCKED; no red proof gives REJECTED; an exception during TESTING resumes without duplicate evaluations; `halt` gives ABORTED; missing kernel slice gives BLOCKED |
| `tests/test_governor_boundaries.py` | Static scan of `src/databossx/governor/`: no `sqlite3.connect`, `socket`, `threading`, `asyncio`, `http.server`, `requests`, `urllib.request`; governor-table writes only in `store.py`; no DDL outside `migrations/`; the sandbox allowlist has no `push`, `tag`, `merge`, or `remote` |

Not modified: `migrations/001_initial_schema.sql`, `orchestrator.py`,
`intake.py`, `api.py` (read-only governor endpoints come later), any
`horizon/` or `backend/` file, any workbook, any `examples/` fixture, any
`_AI_*` packet folder (including this one and PR #116's).

## 3. Build sequence

- [ ] **Phase 0: prerequisites.** 0.1 decided; 0.2 and 0.3 as one verbatim
  commit; 0.4 and 0.5 as separate commits; 0.6 locally. Gate: branch suite
  green except the two v0 tests listed in 1.4, which phase 1 rewrites.
- [ ] **Phase 1: records and storage.** 1.1 migration; `canonical.py`;
  `models.py`, `lease.py`, `envelope.py` revisions; `store.py`; `receipts.py`;
  `hashing.store_bytes_in_vault`; 1.4 rewrites; tests `schema`, `canonical`,
  `lease`, `receipts`, `boundaries`. Gate: full suite green; golden vectors
  match.
- [ ] **Phase 2: decision layer.** `limits.py`, `vetoes.py`, `proposals.py`,
  `ranker.py`, `authorize.py`, CLI `init`, `status`, `approve`, `halt`,
  `resume`, `verify-receipts`; tests `ranker`, `vetoes`, `authorize`. Gate:
  0.4 merged, proven by a test that `limits.capability_allowed("workbook.write")`
  is denied.
- [ ] **Phase 3: execution layer.** `sandbox.py`, `builders.py`,
  `evaluate.py`, `review.py`, `probe_harness.py`, `observe.py`,
  `benchmarks.py`, `learning.py`, `cycle.py`, remaining CLI;
  `config/governor/*`; test `cycle_e2e`. Gate: the toy cycle and all its
  variants pass.
- [ ] **Phase 4: run `gov-cycle-0001`** exactly as `FIRST_CYCLE.md`
  specifies. Expected terminal `CYCLE_ACCEPTED_FOR_INDEPENDENT_REVIEW`, patch
  `9a9a41cd...`. Whether to open a draft PR is a separate human approval. No
  merge.
- [ ] **Phase 5: follow-ups, each its own cycle or reviewed PR.** P-B
  (pending marker, needs human wording), P-C (prose decimal), P-F (scope the
  completeness vocabulary to the schedule header, from RF-1); read-only
  `GET /governor/cycles`; safe deprecation proposals (Issue #68 item 10) that
  can only mark `superseded` or `RETIRED`, never delete.

## 4. Non-goals

- No daemon, scheduler, watcher, socket, webhook, or Drive bridge inside the
  governor. A later Drive readback consumes
  `outbox_events('governor.cycle.closed')` under its own authority.
- No model calls in cycles until route decisions (PR #107 style) are
  canonical; `max_model_calls = 0` until then.
- No PostgreSQL. SQLite `BEGIN IMMEDIATE` plus the lease triggers give the
  single-writer guarantee in the local-first monolith.
- No `gov_*` or `cb_*` table family. PR #67's tournament and judge ideas map
  to `governor_evaluations` (BASELINE versus CANDIDATE on a frozen suite) and
  the kernel `review_gates`.
- Nothing from PR #116's challenger folder, or from this folder, is imported
  or executed.
