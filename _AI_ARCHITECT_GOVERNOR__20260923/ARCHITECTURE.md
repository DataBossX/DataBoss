# Continuous Improvement Governor: architecture

Design only. See `README.md` for isolation rules. Line references are to
branch `cursor/kernel-governor-tournament-7f1f` at `5fc0d6c` unless a PR is
named.

## 1. Decision

**Extend the governor v0 already on this branch (`src/databossx/governor/`,
`migrations/002_governor.sql`). Do not add a second governor, a `gov_*` table
family, or any new approval, audit, outbox, task, or lease store.**

A governor cycle is one `runs` row of workflow `governor_cycle@1.0.0` in the
per-project database for project id `governor`
(`runtime/projects/governor/project.db`, gitignored by `.gitignore:69`). Each
stage is one `tasks` row. Human authorizations are `approvals` rows. Every
state change writes an `audit_events` row in the same transaction. Receipts
are canonical JSON in the content-addressed vault, chained by hash.

The governor adds only records no existing table can hold. It keeps the six
v0 table names (`improvement_proposals`, `task_envelopes`, `writer_leases`,
`cycle_receipts`, `learning_records`, `tournament_rounds`) and adds six
`governor_*` tables (`governor_scope_controls`, `governor_cycles`,
`governor_rank_decisions`, `governor_approval_uses`, `governor_evaluations`,
`governor_benchmark_cases`).

Rationale:

- The OS blueprint requires one orchestrator, one evidence model, one review
  system, and one audit stream. Issue #68 names fragmentation as the main
  risk. Parked PR #67's `cb_approvals`, `cb_leases`, `cb_receipts`,
  `cb_audit_events`, and `cb_jobs` show the failure mode.
- A parallel `gov_*` family next to v0's tables would itself be a second
  control plane. v0's `002_governor.sql` has not merged to `main`, and
  `runtime/` is gitignored, so v0 can be **revised in place** with no data
  migration. Any local `runtime/projects/governor/project.db` built from v0 is
  disposable and must be deleted once. The revised tables are
  `CREATE TABLE IF NOT EXISTS`, so an old file would silently keep v0 columns.
- The blueprint's self-builder limits ("may propose and build; may not deploy
  itself, expand its permissions, change release gates, edit its own audit
  history") map directly onto L0 to L2 autonomy. L3 requires a separate human
  approval, and L4 is outside the governor.

Trade-offs accepted:

- **Kernel dependency.** The governor needs a tracked migration runner, task
  transitions, a deny-by-default capability policy, and review gates. PR #114
  (`e8b9225`) drafts all four. The governor uses them at their canonical paths
  (`src/databossx/database.py`, `tasks.py`, `policy.py`, PR #114's
  `002_kernel_and_connectors.sql`) and never copies them under `governor/`.
  `IMPLEMENTATION_DELTA.md` phase 0 lists the exact slice and one required
  policy fix. Until the slice lands, the governor stays at L0 and L1, which is
  observe and draft only.
- **Step function, not a daemon.** "REPEAT" means an operator, or later a
  scheduler task, calls `databossx governor tick`. There is no listener,
  thread, or hidden loop. At most one cycle is open per scope, enforced by a
  partial unique index.
- **SQLite string time.** Lease and approval expiry compare
  `strftime('%Y-%m-%dT%H:%M:%SZ','now')` strings. A `CHECK ... GLOB` pins the
  format, so v0's `datetime.isoformat()` (`+00:00`) values are rejected rather
  than compared wrongly.

## 2. Existing patterns reused

| Need | Existing mechanism | Where |
| --- | --- | --- |
| Connection, WAL, foreign keys | `DataBossDatabase.connect` | `src/databossx/database.py:22-27` |
| Migrations | `initialize()` re-executes every `migrations/*.sql` on each call (untracked). PR #114 replaces it with a `schema_migrations`-tracked runner | `database.py:29-34`; PR #114 `database.py` |
| Audit write | `DataBossDatabase.audit(...)` | `database.py:55` |
| Per-project paths | `project_db_path`, `project_vault_root`, `ensure_runtime_dirs` | `src/databossx/config.py:29,32,50` |
| Content-addressed vault | `sha256_bytes`, `vault_path`, `copy_file_to_vault` | `src/databossx/hashing.py:21,25,37` |
| Canonical JSON | `json.dumps(sort_keys=True, separators=(",", ":"))` | `src/databossx/intake.py:17-18` |
| Run and task seeding | `seed_project_intake_run` (workflow row, run, tasks, audit) | `src/databossx/orchestrator.py:8-48` |
| Task states, leases | PR #114 `LEGAL_TRANSITIONS`, `transition`, `lease_task`, `expire_stale_leases`, `complete_task` | PR #114 `src/databossx/tasks.py` |
| Capability policy | PR #114 `PolicyEngine.decide`, `EXTERNAL_WRITE_CAPABILITIES`, `allow_external_write` | PR #114 `src/databossx/policy.py` |
| Review | PR #114 `review_gates`, `review_decisions` | PR #114 `migrations/002_kernel_and_connectors.sql` |
| Profile ceilings | `autonomy_ceiling = "L2"`, `auto_merge = false`, `client_evidence = false`, `external_writes = false` | `config/policies/public-safe.toml` |
| Approvals | `approvals(project_id, artifact_hash, approver_id, approved_at, expires_at, payload_json)` | `migrations/001_initial_schema.sql:162-172` |
| Audit, FTS | `audit_events`, `audit_events_fts` | `001_initial_schema.sql:184-211` |
| Outbox | `outbox_events` | `001_initial_schema.sql:174-182` |
| Artifacts | `derived_artifacts`, `artifact_lineage` | `001_initial_schema.sql:76-89` |
| CLI | one `databossx` argparse CLI with governor subcommands | `src/databossx/cli.py:89-113` |
| Publication scan | `scan_publication_policy` | `src/databossx/governor/policy_gate.py` |

## 3. Governor v0 on this branch: disposition

| v0 file | Keep | Defect to fix | Disposition |
| --- | --- | --- | --- |
| `governor/models.py` | `HARD_VETOES` ids, frozen dataclasses | float scores; `reversibility` is free text | `CANONICALIZE_NOW`: integer 1 to 5 scores |
| `governor/envelope.py` | `compile_envelope` entry point | `DEFAULT_ALLOWLIST` (line 12) includes `src/databossx/governor/` and all of `tests/` and `docs/`, which lets a cycle edit the governor itself; `envelope_id` is `uuid4` (line 41), so the id is not reproducible | `CANONICALIZE_NOW`: exact-file write allowlist, V6 protected paths, `envelope_id = envelope_hash[:16]` |
| `governor/lease.py` | API names `acquire_lease`, `assert_lease`, `StaleWriter` | reads `MAX(fence)` then inserts outside a transaction; no check for an unexpired holder, so a second worker "acquires" while the first is live; `isoformat()` times (lines 22, 48) | `CANONICALIZE_NOW`: `BEGIN IMMEDIATE`, DB triggers, `Z` timestamps |
| `governor/ranker.py` | deterministic sort, veto-first | float tuple key | `CANONICALIZE_NOW`: `Fraction` score |
| `governor/cycle.py` | `run_synthetic_cycle` as a thin demo wrapper | `INSERT OR REPLACE` into proposals (line 89); outcome based on file existence (`_missing_regressions`, line 110), not behavior; non-vocabulary terminal `CYCLE_BLOCKED_MISSING_REGRESSIONS` (line 165); no approval, no audit, unchained receipts | `SUPERSEDE_AFTER_PROOF`: replaced by `GovernorCycle.tick` |
| `governor/policy_gate.py` | forbidden-pattern scanner | `_allowlisted` skips every path starting with `_AI_` (line 40), so a leak inside any packet folder passes | `CANONICALIZE_NOW`: scan `_AI_*` for credential and private-key kinds; only the Windows-path kind may be allowlisted |
| `governor/inventory.py`, `tournament.py` | census and packet judging | none blocking | `PRESERVE_AS_TEST_OR_REFERENCE` |
| `migrations/002_governor.sql` | six table names | no constraints, float scores, mutable rows | `CANONICALIZE_NOW`: replaced by section 6 |
| `tests/test_governor.py::test_stale_writer_rejected` | intent | encodes lease stealing: worker-b acquires while worker-a's lease is live | rewrite: worker-b must be refused until expiry or release |

## 4. Components

All paths are under `src/databossx/governor/`. Only `store.py` issues SQL
against governor tables, and only `cycle.py` calls `store.py` mutators, so
"one writer" also holds inside the governor.

| Component | File | Responsibility | Depends on | Level |
| --- | --- | --- | --- | --- |
| Canonical hashing | `canonical.py` (new) | `canonical_json(obj) -> bytes` (sorted keys, compact, UTF-8; rejects `float`, NaN, bytes, non-str keys); `content_hash(obj) -> str` | `hashing.sha256_bytes` | n/a |
| Records | `models.py` (revise) | Frozen dataclasses `ImprovementProposal`, `RankDecision`, `TaskEnvelope`, `Evaluation`, `BenchmarkCase`, `ReviewOutcome`, `LearningRecord`, `CycleReceipt`, `VetoResult`; `HARD_VETOES` and `TERMINAL_STATES` | `canonical` | n/a |
| Vetoes | `vetoes.py` (new) | Pure `V1`..`V6` predicates over proposal, envelope, diff, and output bytes | `limits` | n/a |
| Governor limits | `limits.py` (new; not named `policy.py`, to avoid confusion with the kernel `databossx.policy`) | Loads `config/policies/public-safe.toml` and `config/governor/governor.v1.toml` (protected paths, budget ceilings, synthetic marker). Delegates capability checks to the kernel `PolicyEngine` | kernel `policy.py` | n/a |
| Benchmarks | `benchmarks.py` (new) | Loads reviewed cases from `config/governor/benchmarks/*.json` into `governor_benchmark_cases`; only `ACTIVE` cases run | `store` | L0 |
| Observer | `observe.py` (new) | Runs `ACTIVE` probes against the base tree in a read-only worktree; a `Finding` is a probe whose expectation fails. Reads an operator-supplied open-PR snapshot file; never calls the network | `sandbox`, `benchmarks` | L0 |
| Proposal compiler | `proposals.py` (new) | `Finding` to an immutable `ImprovementProposal` with evidence, target, deterministic scores, write paths, and duplicate check | `models` | L0 |
| Ranker | `ranker.py` (revise) | Vetoes first, then `Fraction` score; returns `RankDecision` | `vetoes` | L0 |
| Envelope compiler | `envelope.py` (revise) | Compiles, validates, and seals the envelope (`TASK_ENVELOPE.md`) | `canonical`, `limits`, `vetoes` | L1 |
| Writer lease | `lease.py` (revise) | `acquire`, `heartbeat`, `release`, `assert_current`, `halt`, `resume`; each in `BEGIN IMMEDIATE` | `store` | n/a |
| Authorization | `authorize.py` (new) | Consumes a human `approvals` row into `governor_approval_uses`; the DB trigger checks hash, project, and expiry. Never creates approvals | `store` | gate |
| Sandbox | `sandbox.py` (new) | `git worktree add --detach` at the base commit under `runtime/governor/worktrees/<cycle_key>`; environment built from `env_allowlist` only; diff, tree SHA, teardown | stdlib `subprocess` | L2 |
| Evaluator | `evaluate.py` (new) | Runs pytest node sets with `--junitxml`; records counts, `outcome_set_hash`, `command_hash`, `env_manifest_hash`, tree SHA | `sandbox`, `store` | L2, L3 |
| Review bridge | `review.py` (new) | Opens a kernel `review_gates` row (`gate_type='governor.independent_review'`), stores the review bundle, reads `review_decisions` | kernel tables | gate |
| Receipts | `receipts.py` (new) | Builds `CycleReceipt`, links `prev_receipt_hash`, writes vault bytes, registers `derived_artifacts`, verifies the chain | `canonical`, `hashing` | n/a |
| Learning | `learning.py` (new) | Candidate records from cycle facts only; human review is final | `store` | L1 |
| Store | `store.py` (new) | The only SQL against governor tables; every mutator writes `audit_events` in the same transaction | `database` | n/a |
| Cycle driver | `cycle.py` (revise) | `GovernorCycle.tick(scope)` advances exactly one stage; closes with exactly one receipt | all of the above | orchestrator |
| Census, packet judge | `inventory.py`, `tournament.py` (keep) | Unchanged; feed OBSERVE as read-only facts | n/a | L0 |

Nothing in the governor opens a socket, starts a thread, calls a model, or
reads outside the repository worktree and `runtime/projects/governor/`.

## 5. Autonomy levels mapped to stages

| Level | Stages | Allowed | Forbidden |
| --- | --- | --- | --- |
| L0 Observe | OBSERVE, PROPOSE, PRIORITIZE | Read the base tree; run `ACTIVE` probes read-only; write proposals and rank decisions | Any repository write |
| L1 Draft | envelope seal, LEARN | Write `task_envelopes` and candidate `learning_records` | Runtime mutation, repository write |
| L2 Isolated implementation | BUILD, TEST, rollback rehearsal | Write only `write_allowlist` files inside the cycle worktree; local commit on a detached worktree | Push, PR, merge, egress, any other path |
| L3 Private canary | CANARY | Run the candidate on the synthetic fixtures named in the envelope | Non-synthetic input. Needs a human `AUTHORIZE_L3_CANARY` approval, because `public-safe.toml` caps autonomy at L2 |
| L4 External action or release | none | The governor emits a patch bundle. A human `OPEN_DRAFT_PR` approval bound to the patch hash and destination is consumed by the operator's own tool. Merge, deploy, release, and hold removal are human-only | Everything, autonomously |

## 6. Migration: revised `migrations/002_governor.sql`

**File name.** Keep the branch's `002_governor.sql`. PR #114
(`002_kernel_and_connectors.sql`) and PR #107 (`002_engine_tables.sql`) also
use prefix `002`. File names differ, the tracked runner keys on file name, and
no object names collide, so all three can coexist. Sorted order runs
`002_engine_tables`, then `002_governor`, then `002_kernel_and_connectors`.
The governor file has no foreign key into PR #107 or PR #114 tables, so order
does not matter.

**Collision check (verified by script, see `RECEIPT.md`).** 45 objects, 0
collisions against `001_initial_schema.sql` (30 objects), PR #114 `002` (11:
`task_manifests`, `connector_cursors`, `evidence_spans`, `claims`,
`claim_support`, `conflicts`, `review_gates`, `review_decisions`, and 3
indexes), PR #107 `002` (7), and parked PR #67 `cb_*` (49). No `ALTER TABLE`.
No `tasks`, `approvals`, `audit_events`, `outbox_events`, or `task_leases`
DDL.

**Runner compatibility (verified).** The file applies twice under the
branch's untracked re-run-every-file runner. It also applies alongside PR
#114's `002` under a `schema_migrations`-tracked runner. PR #114's `002`
**crashes** on a second untracked `initialize()` (`duplicate column name:
input_manifest_hash`), because it runs `ALTER TABLE tasks`. The tracked
runner is therefore a hard prerequisite for porting any PR #114 schema.
With PR #114's `database.py`, `tasks.py`, `policy.py`, and `002` copied
byte-identical onto `5fc0d6c` and this file in place, the suite gives 173
passed and 2 failed. The two failures are the v0 tests
`test_stale_writer_rejected` and `test_synthetic_cycle_and_census`, which
the new constraints reject by design (`+00:00` lease times, proposals with
no scope). They are rewritten in the same commit as the schema.

### 6.1 SQL

The block below is byte-identical to the verified file (SHA-256
`a49ccd173e6b8cf99296897f9cc06975bae5783af0c588feacd0f528f7818567`, 397 lines including the trailing newline).

```sql
-- Continuous Improvement Governor tables (revision of the branch's 002 before first merge).
-- Keeps the six v0 table names; adds governor_* tables. No claims/evidence/connector,
-- review, approval, audit, outbox, task, or lease-per-task tables. No ALTER TABLE.

CREATE TABLE IF NOT EXISTS improvement_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL,
    title TEXT NOT NULL,
    proposal_class TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    value_score INTEGER NOT NULL CHECK (typeof(value_score) = 'integer' AND value_score BETWEEN 1 AND 5),
    risk_score INTEGER NOT NULL CHECK (typeof(risk_score) = 'integer' AND risk_score BETWEEN 1 AND 5),
    cost_score INTEGER NOT NULL CHECK (typeof(cost_score) = 'integer' AND cost_score BETWEEN 1 AND 5),
    reversibility INTEGER NOT NULL CHECK (typeof(reversibility) = 'integer' AND reversibility BETWEEN 1 AND 5),
    confidence INTEGER NOT NULL CHECK (typeof(confidence) = 'integer' AND confidence BETWEEN 1 AND 5),
    autonomy_level TEXT NOT NULL CHECK (autonomy_level IN ('L0', 'L1', 'L2', 'L3', 'L4')),
    vetoes_json TEXT NOT NULL DEFAULT '[]',
    proposal_json TEXT NOT NULL,
    proposal_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN (
        'proposed', 'vetoed', 'ranked', 'selected', 'in_cycle',
        'accepted', 'rejected', 'deferred', 'superseded'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER IF NOT EXISTS improvement_proposals_no_replace
BEFORE INSERT ON improvement_proposals
WHEN EXISTS (SELECT 1 FROM improvement_proposals WHERE proposal_id = new.proposal_id)
BEGIN
    SELECT RAISE(ABORT, 'improvement_proposals are immutable; register a new proposal');
END;

CREATE TRIGGER IF NOT EXISTS improvement_proposals_content_immutable
BEFORE UPDATE OF proposal_id, scope, title, proposal_class, evidence_json, value_score,
    risk_score, cost_score, reversibility, confidence, autonomy_level, vetoes_json,
    proposal_json, proposal_hash ON improvement_proposals
BEGIN
    SELECT RAISE(ABORT, 'improvement_proposals content is immutable');
END;

CREATE TRIGGER IF NOT EXISTS improvement_proposals_no_delete
BEFORE DELETE ON improvement_proposals
BEGIN
    SELECT RAISE(ABORT, 'improvement_proposals is append-only');
END;

CREATE TABLE IF NOT EXISTS governor_scope_controls (
    scope TEXT PRIMARY KEY,
    halted INTEGER NOT NULL DEFAULT 0 CHECK (halted IN (0, 1)),
    halted_reason TEXT NOT NULL DEFAULT '',
    consecutive_non_accepted INTEGER NOT NULL DEFAULT 0 CHECK (consecutive_non_accepted >= 0),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS writer_leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    fence INTEGER NOT NULL CHECK (fence >= 1),
    leased_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    expires_at TEXT NOT NULL CHECK (expires_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
    released_at TEXT NULL CHECK (released_at IS NULL OR released_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
    UNIQUE(scope, fence)
);

CREATE TRIGGER IF NOT EXISTS writer_leases_monotonic_fence
BEFORE INSERT ON writer_leases
WHEN new.fence <= (SELECT COALESCE(MAX(fence), 0) FROM writer_leases WHERE scope = new.scope)
BEGIN
    SELECT RAISE(ABORT, 'fence must increase monotonically per scope');
END;

CREATE TRIGGER IF NOT EXISTS writer_leases_single_holder
BEFORE INSERT ON writer_leases
WHEN EXISTS (
    SELECT 1 FROM writer_leases
     WHERE scope = new.scope
       AND released_at IS NULL
       AND expires_at > strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
)
BEGIN
    SELECT RAISE(ABORT, 'scope already has an unexpired writer');
END;

CREATE TRIGGER IF NOT EXISTS writer_leases_halted_scope
BEFORE INSERT ON writer_leases
WHEN EXISTS (SELECT 1 FROM governor_scope_controls WHERE scope = new.scope AND halted = 1)
BEGIN
    SELECT RAISE(ABORT, 'scope is halted');
END;

CREATE TRIGGER IF NOT EXISTS writer_leases_identity_immutable
BEFORE UPDATE OF scope, worker_id, fence, leased_at ON writer_leases
BEGIN
    SELECT RAISE(ABORT, 'lease identity is immutable');
END;

CREATE TRIGGER IF NOT EXISTS writer_leases_no_reopen
BEFORE UPDATE OF released_at, expires_at ON writer_leases
WHEN old.released_at IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'released lease is final');
END;

CREATE TRIGGER IF NOT EXISTS writer_leases_no_delete
BEFORE DELETE ON writer_leases
BEGIN
    SELECT RAISE(ABORT, 'writer_leases is append-only');
END;

CREATE TABLE IF NOT EXISTS governor_cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_key TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL,
    run_id INTEGER NOT NULL UNIQUE REFERENCES runs(id) ON DELETE RESTRICT,
    stage TEXT NOT NULL CHECK (stage IN (
        'OBSERVING', 'PROPOSING', 'PRIORITIZING', 'AWAITING_AUTHORIZATION',
        'BUILDING', 'TESTING', 'REVIEWING', 'CANARYING', 'DECIDING',
        'LEARNING', 'CLOSED'
    )),
    base_commit TEXT NOT NULL,
    selected_proposal_id TEXT NULL REFERENCES improvement_proposals(proposal_id) ON DELETE RESTRICT,
    envelope_hash TEXT NULL,
    fence_at_authorize INTEGER NULL,
    candidate_patch_sha256 TEXT NULL,
    terminal_state TEXT NULL CHECK (terminal_state IS NULL OR terminal_state IN (
        'CYCLE_ACCEPTED_FOR_INDEPENDENT_REVIEW',
        'CYCLE_REJECTED_WITH_ACTIONABLE_DEFECTS',
        'CYCLE_BLOCKED_REQUIRES_AUTHORITY_OR_BASELINE',
        'CYCLE_ABORTED_BUDGET_OR_STOP',
        'CYCLE_NOOP_NO_ELIGIBLE_PROPOSAL'
    )),
    terminal_reason TEXT NOT NULL DEFAULT '',
    opened_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    closed_at TEXT NULL,
    CHECK ((terminal_state IS NULL) = (stage <> 'CLOSED'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_governor_cycles_one_open_per_scope
    ON governor_cycles(scope) WHERE terminal_state IS NULL;

CREATE TABLE IF NOT EXISTS task_envelopes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    envelope_id TEXT NOT NULL UNIQUE,
    proposal_id TEXT NOT NULL REFERENCES improvement_proposals(proposal_id) ON DELETE RESTRICT,
    cycle_id INTEGER NULL UNIQUE REFERENCES governor_cycles(id) ON DELETE RESTRICT,
    base_commit TEXT NOT NULL,
    schema_id TEXT NOT NULL,
    autonomy_level TEXT NOT NULL CHECK (autonomy_level IN ('L0', 'L1', 'L2', 'L3')),
    payload_json TEXT NOT NULL,
    envelope_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL CHECK (expires_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'),
    state TEXT NOT NULL CHECK (state IN ('COMPILED', 'SEALED', 'AUTHORIZED', 'CONSUMED', 'EXPIRED', 'VOID')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER IF NOT EXISTS task_envelopes_content_immutable
BEFORE UPDATE OF envelope_id, proposal_id, cycle_id, base_commit, schema_id, autonomy_level,
    payload_json, envelope_hash, expires_at ON task_envelopes
BEGIN
    SELECT RAISE(ABORT, 'sealed envelope content is immutable');
END;

CREATE TRIGGER IF NOT EXISTS task_envelopes_no_delete
BEFORE DELETE ON task_envelopes
BEGIN
    SELECT RAISE(ABORT, 'task_envelopes is append-only');
END;

CREATE TABLE IF NOT EXISTS cycle_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id TEXT NOT NULL UNIQUE,
    cycle_id INTEGER NOT NULL UNIQUE REFERENCES governor_cycles(id) ON DELETE RESTRICT,
    envelope_hash TEXT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN (
        'CYCLE_ACCEPTED_FOR_INDEPENDENT_REVIEW',
        'CYCLE_REJECTED_WITH_ACTIONABLE_DEFECTS',
        'CYCLE_BLOCKED_REQUIRES_AUTHORITY_OR_BASELINE',
        'CYCLE_ABORTED_BUDGET_OR_STOP',
        'CYCLE_NOOP_NO_ELIGIBLE_PROPOSAL'
    )),
    payload_json TEXT NOT NULL,
    receipt_hash TEXT NOT NULL UNIQUE,
    prev_receipt_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER IF NOT EXISTS cycle_receipts_chain
BEFORE INSERT ON cycle_receipts
WHEN new.prev_receipt_hash <> COALESCE(
    (SELECT receipt_hash FROM cycle_receipts ORDER BY id DESC LIMIT 1), 'GENESIS'
)
BEGIN
    SELECT RAISE(ABORT, 'prev_receipt_hash must equal the latest receipt_hash');
END;

CREATE TRIGGER IF NOT EXISTS cycle_receipts_append_only_update
BEFORE UPDATE ON cycle_receipts
BEGIN
    SELECT RAISE(ABORT, 'cycle_receipts is append-only');
END;

CREATE TRIGGER IF NOT EXISTS cycle_receipts_append_only_delete
BEFORE DELETE ON cycle_receipts
BEGIN
    SELECT RAISE(ABORT, 'cycle_receipts is append-only');
END;

CREATE TRIGGER IF NOT EXISTS governor_cycles_close_requires_receipt
BEFORE UPDATE OF terminal_state ON governor_cycles
WHEN new.terminal_state IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM cycle_receipts WHERE cycle_id = new.id AND outcome = new.terminal_state
)
BEGIN
    SELECT RAISE(ABORT, 'write the matching terminal receipt before closing the cycle');
END;

CREATE TRIGGER IF NOT EXISTS governor_cycles_frozen_after_close
BEFORE UPDATE ON governor_cycles
WHEN old.terminal_state IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'closed cycle is immutable');
END;

CREATE TRIGGER IF NOT EXISTS governor_cycles_no_delete
BEFORE DELETE ON governor_cycles
BEGIN
    SELECT RAISE(ABORT, 'governor_cycles is append-only');
END;

CREATE TABLE IF NOT EXISTS governor_rank_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL UNIQUE REFERENCES governor_cycles(id) ON DELETE RESTRICT,
    ranker_version TEXT NOT NULL,
    candidate_set_hash TEXT NOT NULL,
    ranking_json TEXT NOT NULL,
    decision_hash TEXT NOT NULL UNIQUE,
    selected_proposal_id TEXT NULL REFERENCES improvement_proposals(proposal_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER IF NOT EXISTS governor_rank_decisions_append_only_update
BEFORE UPDATE ON governor_rank_decisions
BEGIN
    SELECT RAISE(ABORT, 'governor_rank_decisions is append-only');
END;

CREATE TRIGGER IF NOT EXISTS governor_rank_decisions_append_only_delete
BEFORE DELETE ON governor_rank_decisions
BEGIN
    SELECT RAISE(ABORT, 'governor_rank_decisions is append-only');
END;

CREATE TABLE IF NOT EXISTS governor_approval_uses (
    approval_id INTEGER PRIMARY KEY REFERENCES approvals(id) ON DELETE RESTRICT,
    envelope_hash TEXT NOT NULL REFERENCES task_envelopes(envelope_hash) ON DELETE RESTRICT,
    purpose TEXT NOT NULL CHECK (purpose IN ('AUTHORIZE_L2', 'AUTHORIZE_L3_CANARY', 'OPEN_DRAFT_PR')),
    bound_hash TEXT NOT NULL,
    fence INTEGER NOT NULL,
    consumed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(envelope_hash, purpose)
);

CREATE TRIGGER IF NOT EXISTS governor_approval_uses_bound_and_live
BEFORE INSERT ON governor_approval_uses
WHEN NOT EXISTS (
    SELECT 1 FROM approvals
     WHERE id = new.approval_id
       AND artifact_hash = new.bound_hash
       AND project_id = 'governor'
       AND expires_at IS NOT NULL
       AND expires_at > strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
)
BEGIN
    SELECT RAISE(ABORT, 'approval must be a live governor approval of exactly this hash');
END;

CREATE TRIGGER IF NOT EXISTS governor_approval_uses_append_only_update
BEFORE UPDATE ON governor_approval_uses
BEGIN
    SELECT RAISE(ABORT, 'approval uses are single-use and append-only');
END;

CREATE TRIGGER IF NOT EXISTS governor_approval_uses_append_only_delete
BEFORE DELETE ON governor_approval_uses
BEGIN
    SELECT RAISE(ABORT, 'approval uses are single-use and append-only');
END;

CREATE TABLE IF NOT EXISTS governor_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL REFERENCES governor_cycles(id) ON DELETE RESTRICT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
    role TEXT NOT NULL CHECK (role IN (
        'BASELINE', 'RED_PROOF', 'CANDIDATE', 'RERUN', 'ROLLBACK_REHEARSAL', 'CANARY'
    )),
    suite TEXT NOT NULL,
    tree_sha TEXT NOT NULL,
    command_hash TEXT NOT NULL,
    env_manifest_hash TEXT NOT NULL,
    passed INTEGER NOT NULL,
    failed INTEGER NOT NULL,
    skipped INTEGER NOT NULL,
    outcome_set_hash TEXT NOT NULL,
    fence INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_governor_evaluations_cycle ON governor_evaluations(cycle_id, role, suite);

CREATE TRIGGER IF NOT EXISTS governor_evaluations_append_only
BEFORE UPDATE ON governor_evaluations
BEGIN
    SELECT RAISE(ABORT, 'governor_evaluations is append-only');
END;

CREATE TRIGGER IF NOT EXISTS governor_evaluations_no_delete
BEFORE DELETE ON governor_evaluations
BEGIN
    SELECT RAISE(ABORT, 'governor_evaluations is append-only');
END;

CREATE TABLE IF NOT EXISTS governor_benchmark_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_key TEXT NOT NULL,
    case_version INTEGER NOT NULL,
    suite TEXT NOT NULL CHECK (suite IN ('invariant', 'golden', 'adversarial', 'canary')),
    target_ref TEXT NOT NULL,
    issue_ref TEXT NOT NULL DEFAULT '',
    case_json TEXT NOT NULL,
    case_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('DRAFT', 'REVIEWED', 'ACTIVE', 'RETIRED')),
    reviewed_by TEXT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(case_key, case_version),
    CHECK (status IN ('DRAFT') OR reviewed_by IS NOT NULL)
);

CREATE TRIGGER IF NOT EXISTS governor_benchmark_cases_content_immutable
BEFORE UPDATE OF case_key, case_version, suite, target_ref, issue_ref, case_json, case_hash
    ON governor_benchmark_cases
BEGIN
    SELECT RAISE(ABORT, 'benchmark case content is immutable; add a new case_version');
END;

CREATE TRIGGER IF NOT EXISTS governor_benchmark_cases_no_delete
BEFORE DELETE ON governor_benchmark_cases
BEGIN
    SELECT RAISE(ABORT, 'retire benchmark cases instead of deleting them');
END;

CREATE TABLE IF NOT EXISTS learning_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL UNIQUE,
    source_receipt_id TEXT NOT NULL REFERENCES cycle_receipts(receipt_id) ON DELETE RESTRICT,
    claim TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'reviewed_accepted', 'reviewed_rejected')),
    reviewed_by TEXT NULL,
    reviewed_at TEXT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((status = 'candidate') = (reviewed_by IS NULL))
);

CREATE TRIGGER IF NOT EXISTS learning_records_content_immutable
BEFORE UPDATE OF record_id, source_receipt_id, claim, evidence_json, record_hash ON learning_records
BEGIN
    SELECT RAISE(ABORT, 'learning record content is immutable');
END;

CREATE TRIGGER IF NOT EXISTS learning_records_review_is_final
BEFORE UPDATE OF status, reviewed_by, reviewed_at ON learning_records
WHEN old.status <> 'candidate'
BEGIN
    SELECT RAISE(ABORT, 'learning review decision is final');
END;

CREATE TRIGGER IF NOT EXISTS learning_records_no_delete
BEFORE DELETE ON learning_records
BEGIN
    SELECT RAISE(ABORT, 'learning_records is append-only');
END;

CREATE TABLE IF NOT EXISTS tournament_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id TEXT NOT NULL UNIQUE,
    folder_glob TEXT NOT NULL,
    scorecard_json TEXT NOT NULL,
    winner_folder TEXT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON improvement_proposals(status, id);
CREATE INDEX IF NOT EXISTS idx_envelopes_state ON task_envelopes(state, id);
```

### 6.2 Invariants the schema enforces (all exercised; 67 of 67 checks pass)

| Invariant | Mechanism |
| --- | --- |
| Proposals cannot be replaced, edited, or deleted; only `status` moves | `improvement_proposals_no_replace` (a `BEFORE INSERT` trigger, because delete triggers do not fire on `REPLACE` unless `recursive_triggers` is on), `_content_immutable`, `_no_delete` |
| Scores are integers 1 to 5 | `CHECK (typeof(x) = 'integer' AND x BETWEEN 1 AND 5)`; `INTEGER` affinity alone accepts `4.5` |
| One live writer per scope; fences strictly increase; halted scopes refuse writers | `writer_leases_single_holder`, `_monotonic_fence`, `_halted_scope`, `UNIQUE(scope, fence)` |
| Lease identity is fixed; a released lease cannot reopen; leases are never deleted | `writer_leases_identity_immutable`, `_no_reopen`, `_no_delete` |
| Expiry strings are comparable | `CHECK (expires_at GLOB '....-..-..T..:..:..Z')` on leases and envelopes |
| At most one open cycle per scope | partial unique index `idx_governor_cycles_one_open_per_scope` |
| A cycle closes only with a matching terminal receipt; closed cycles are frozen | `governor_cycles_close_requires_receipt`, `_frozen_after_close`, `CHECK ((terminal_state IS NULL) = (stage <> 'CLOSED'))` |
| Receipts form one hash chain and are append-only | `cycle_receipts_chain` (`prev_receipt_hash` must equal the latest `receipt_hash`, or `GENESIS`), `_append_only_update`, `_append_only_delete` |
| An envelope is never L4; sealed content is immutable | `CHECK autonomy_level IN ('L0','L1','L2','L3')`, `task_envelopes_content_immutable`, `_no_delete` |
| An approval is used once, is live, is for the governor project, and binds exactly the used hash | `governor_approval_uses.approval_id` primary key, `UNIQUE(envelope_hash, purpose)`, `governor_approval_uses_bound_and_live` |
| Evaluations and rank decisions are append-only | `governor_evaluations_append_only`, `_no_delete`; `governor_rank_decisions_append_only_*` |
| Learning review needs a named reviewer and is final | `CHECK ((status = 'candidate') = (reviewed_by IS NULL))`, `learning_records_review_is_final`, `_no_delete` |
| Benchmark cases need a reviewer before activation; content is versioned, never edited | `CHECK (status IN ('DRAFT') OR reviewed_by IS NOT NULL)`, `governor_benchmark_cases_content_immutable`, `_no_delete` |

The schema cannot check that the approver is a human who differs from the
builder. `authorize.py` rejects an `approver_id` equal to any
`writer_leases.worker_id` for the scope, or beginning with `governor`.

### 6.3 Existing tables, used without schema change

| Table | Governor usage |
| --- | --- |
| `jurisdictions` | one row `('SYNTHETIC', 'SYNTHETIC')` |
| `projects` | one row `id='governor'`, `policy_version='governor-policy/1'`, `status='GOVERNOR_ACTIVE'`; no `title_projects` row. `create_project` ids are 12 hex characters, so `governor` cannot collide |
| `workflow_definitions` | `('governor_cycle', '1.0.0')` |
| `runs` | one per cycle, referenced by `governor_cycles.run_id` |
| `tasks` (+ kernel `task_manifests`) | one task per stage: `GOV_OBSERVE`, `GOV_PROPOSE`, `GOV_PRIORITIZE`, `GOV_AUTHORIZE`, `GOV_BUILD`, `GOV_TEST`, `GOV_REVIEW`, `GOV_CANARY`, `GOV_DECIDE`, `GOV_LEARN`; idempotency key `sha256(cycle_key:stage:envelope_hash)` |
| `task_dependencies` | strict chain between stage tasks |
| `task_leases`, `task_attempts` | per-task worker leases for BUILD, TEST, CANARY. `writer_leases` is the per-scope fence above them, not a replacement |
| `approvals` | human-created only; `project_id='governor'`; `artifact_hash` is the bound hash; `expires_at` is required and uses the `Z` format; `payload_json` holds `{"kind":"governor","purpose":...,"scope":...,"hold_attested":true}` |
| kernel `review_gates`, `review_decisions` | `gate_type='governor.independent_review'`; decisions `APPROVE`, `REQUEST_CHANGES`, `BLOCK` |
| `derived_artifacts` | `governor.cycle_receipt`, `governor.patch`, `governor.junit_report`, `governor.review_bundle` |
| `audit_events` | every governor mutation |
| `outbox_events` | `governor.cycle.closed` only, for a later, separately gated readback bridge |

## 7. State machines

### 7.1 Cycle (`governor_cycles.stage`)

```text
OBSERVING -> PROPOSING -> PRIORITIZING -> AWAITING_AUTHORIZATION -> BUILDING
  -> TESTING -> REVIEWING -> CANARYING -> DECIDING -> LEARNING -> CLOSED

OBSERVING | PROPOSING | PRIORITIZING, with no finding or all vetoed -> LEARNING (NOOP)
AWAITING_AUTHORIZATION, with approval missing, expired, or denied    -> LEARNING (BLOCKED)
BUILDING .. DECIDING, on any gate failure                            -> LEARNING (REJECTED or BLOCKED)
any non-CLOSED stage, on halt, budget, stale fence, or base drift    -> LEARNING (ABORTED or BLOCKED)
```

Rules:

- `tick()` advances exactly one stage per call while holding the scope lease.
  On every call it re-checks the fence, the halt flag, the base commit, the
  envelope input hashes, and the envelope expiry.
- Stage task *N+1* is created only when task *N* has succeeded. Every path
  runs LEARNING, so every cycle ends with exactly one receipt and one learning
  candidate.
- Terminal states (Issue #69 vocabulary adapted to cycles; the same five
  strings are the SQL `CHECK` values):

| Terminal state | When |
| --- | --- |
| `CYCLE_ACCEPTED_FOR_INDEPENDENT_REVIEW` | All gates green, independent review `APPROVE`, canary green. The output is a patch bundle for a human; nothing is pushed |
| `CYCLE_REJECTED_WITH_ACTIONABLE_DEFECTS` | A candidate was built but a red-proof, scope, test, reproducibility, rollback, review, or canary gate failed. The receipt lists each defect with its gate id |
| `CYCLE_BLOCKED_REQUIRES_AUTHORITY_OR_BASELINE` | Approval missing or expired, unknown or conflicting writer, stale fence, base or input drift, baseline not green, or kernel slice absent |
| `CYCLE_ABORTED_BUDGET_OR_STOP` | Budget exceeded, or the scope was halted |
| `CYCLE_NOOP_NO_ELIGIBLE_PROPOSAL` | No finding, or every proposal was vetoed |

- **Circuit breaker.** Three consecutive terminals other than ACCEPTED or NOOP
  in one scope set `governor_scope_controls.halted = 1` with reason
  `circuit_breaker`. Only a human `databossx governor resume` clears it.
- **Finite.** Each `tick` does bounded work, and each cycle has an expiring
  envelope and integer budgets. A new cycle cannot open while one is open. A
  cycle can never target governor code, policy, migrations, or CI (V6), so the
  loop cannot widen its own permissions.

### 7.2 Proposal (`improvement_proposals.status`)

```text
proposed -> vetoed
proposed -> ranked -> selected -> in_cycle -> accepted | rejected
            ranked -> deferred (not selected; re-ranked next cycle)
any non-terminal -> superseded (an accepted proposal or a merged PR made it moot)
```

Content is immutable. A changed idea is a new proposal with a new hash.
`proposal_id` is `proposal_key` plus `-` plus `proposal_hash[:12]`.

### 7.3 Envelope (`task_envelopes.state`)

```text
COMPILED (memory only) -> SEALED (row inserted, hash unique)
SEALED -> AUTHORIZED (AUTHORIZE_L2 use recorded with fence)
AUTHORIZED -> CONSUMED (cycle closed)
SEALED | AUTHORIZED -> EXPIRED (now >= expires_at) | VOID (cycle ended before use)
```

Any change to base, inputs, allowlists, capabilities, budgets, or tests makes
a new envelope, which needs a new approval.

### 7.4 Writer lease (`writer_leases`, one row per grant)

```text
no live row -> acquire -> live(fence = max + 1, holder, expires_at)
live -> heartbeat -> live (same row; expires_at extended; fence unchanged)
live -> release -> released (released_at set; final)
live -> expiry -> dead; the next acquire gets fence + 1, and the old holder's writes fail
halted scope -> acquire refused until a human resumes
```

`acquire` runs inside `BEGIN IMMEDIATE`, so SQLite's writer lock serializes
competing acquirers, and the triggers refuse a second live holder even if the
Python check is bypassed. Every governor write carries the fence, and
`store.py` checks, in the same transaction, that the caller's row is the
highest fence, unreleased, and unexpired. A stale writer raises `StaleWriter`
and the cycle ends BLOCKED `stale_fence`. This is Issue #68's
"database-enforced writer lease and monotonic fencing sequence per scope".
It sits above the kernel's per-task `task_leases` and does not replace them.

### 7.5 Learning record and benchmark case

```text
learning:  candidate -> reviewed_accepted | reviewed_rejected   (human, final)
benchmark: DRAFT -> REVIEWED -> ACTIVE -> RETIRED               (human for REVIEWED)
```

Only a `reviewed_accepted` learning record may seed a `DRAFT` benchmark case
or change a ranker confidence rule. Model prose never becomes a learning
record. Records hold structured cycle facts: which probe fired, which gates
failed, and the score versus the outcome.

## 8. Ranking (`NextBestMove`)

1. Drop vetoed proposals (status `vetoed`, with the veto id).
2. Drop proposals whose write paths exceed the governor's `max_files_changed`
   or touch protected paths (V6).
3. Score = `Fraction(value * confidence * reversibility, risk * cost)`. Each
   field is an integer from 1 to 5, set by the deterministic rules below. No
   floats and no model-generated scores.
4. Order by score descending, then risk ascending, then `proposal_hash`
   ascending.
5. Select the first. Persist the full table as `ranking_json` and
   `candidate_set_hash = content_hash(sorted proposal hashes)`.

| Field | Rule |
| --- | --- |
| value | 5: the probe maps to a named mandatory regression in an open P0 issue, or to a governor safety defect. 4: fabrication or a silent value change. 3: other correctness. 2: docs or tests only |
| risk | 1: the change is inside one fail-closed predicate and only removes positives. 2: it widens a shared vocabulary or regex. 3: it widens a parser (new facts may appear), public API, or schema. 4 or more is never auto-selected |
| cost | 1: at most 2 files and 80 added lines. 2: at most 5 files. Otherwise 3 or more |
| reversibility | 5: one commit, revertible, no data migration. 3: migration involved. 1: external effect |
| confidence | 5: reproduced deterministically twice, with a guard case passing. 3: reproduced once, or the right fix is ambiguous. 1: inferred |

## 9. Receipts

### 9.1 Cycle receipt (one per cycle, mandatory)

Canonical JSON (`TASK_ENVELOPE.md` section 2), stored as vault bytes under
`runtime/projects/governor/vault/sha256/<h[:2]>/<h>`, registered as
`derived_artifacts(artifact_type='governor.cycle_receipt')`, inserted into
`cycle_receipts` (hash-chained), and announced by `audit_events` and
`outbox_events('governor.cycle.closed')`.

```json
{
  "schema": "databossx.governor.cycle_receipt/1",
  "cycle_key": "gov-cycle-0001",
  "scope": "repo:DataBossX/DataBoss",
  "terminal_state": "CYCLE_ACCEPTED_FOR_INDEPENDENT_REVIEW",
  "terminal_reason": "all blocking gates passed",
  "base": {"commit": "<40 hex>", "tree": "<40 hex>"},
  "proposal_hash": "<64 hex>",
  "rank_decision_hash": "<64 hex>",
  "envelope_hash": "<64 hex>",
  "fence": 1,
  "approvals": [{"purpose": "AUTHORIZE_L2", "approval_id": 1, "bound_hash": "<envelope_hash>"}],
  "candidate": {"patch_sha256": "<64 hex>", "tree": "<40 hex>", "files_changed": ["..."], "added_lines": 0, "removed_lines": 0},
  "evaluations": [{"role": "BASELINE", "suite": "golden", "tree": "<40 hex>", "passed": 0, "failed": 0, "skipped": 0,
                   "outcome_set_hash": "<64 hex>", "command_hash": "<64 hex>", "env_manifest_hash": "<64 hex>"}],
  "veto_results": [{"id": "V1_CLIENT_EVIDENCE", "stage": "PRE_DECIDE", "result": "CLEAR"}],
  "gates": [{"id": "G_BASELINE_GREEN", "result": "PASS"}],
  "review": {"review_gate_id": 1, "decision": "APPROVE", "findings": [{"id": "RF-1", "blocking": false}]},
  "canary": {"fixture": "grocery_report_pipeline.make_synthetic_corpus", "result": "PASS"},
  "rollback_rehearsal": {"result": "PASS", "red_again_at_revert": true, "tree_restored": true},
  "budgets_used": {"files_changed": 0, "test_invocations": 0, "model_calls": 0, "cost_usd_cents": 0},
  "learning_record_hash": "<64 hex>",
  "audit_event_range": {"first_id": 1, "last_id": 1},
  "safety": {"CLIENT_BYTES_MUTATED": "NO", "CLIENT_EVIDENCE_READ": "NO", "WORKBOOK_MUTATED": "NO",
             "EXTERNAL_RELEASE": "NO", "MERGED": "NO", "SECRETS_IN_OUTPUT": "NO", "NEW_CONTROL_PLANE_OBJECTS": "NO"},
  "prev_receipt_hash": "GENESIS",
  "produced_by": "databossx.governor/0.2.0",
  "closed_at": "<YYYY-MM-DDTHH:MM:SSZ>"
}
```

The first receipt uses `GENESIS` as `prev_receipt_hash`; the SQL trigger
enforces the link. Integers only; no floats anywhere in a receipt.
`receipt_id = receipt_hash[:16]`.

### 9.2 Verification (`databossx governor verify-receipts`)

For each receipt in id order: the vault bytes hash to `receipt_hash`;
`prev_receipt_hash` equals the previous `receipt_hash`; `envelope_hash`
exists in `task_envelopes`, unless the terminal is NOOP; every referenced
approval exists in `approvals` and `governor_approval_uses`; and the audit id
range contains `governor.cycle.closed` for the cycle. Any mismatch exits
non-zero and halts the scope.

### 9.3 Redaction

A veto or secret-scan hit records only the rule id, repository-relative path,
and line number, never the matched text. Receipts contain no absolute host
paths.

## 10. Data flow (one cycle)

```text
operator: databossx governor tick --scope repo:DataBossX/DataBoss
  |
  v
cycle.tick -> lease.acquire (BEGIN IMMEDIATE; fence + 1) -> halted? -> ABORTED
  |
  +- OBSERVING     sandbox.read_only(base) -> observe.run_probes(ACTIVE cases) -> Findings
  +- PROPOSING     proposals.compile(Findings, open-PR snapshot) -> improvement_proposals
  +- PRIORITIZING  vetoes + ranker.rank -> governor_rank_decisions
  +- AWAITING_AUTHORIZATION  envelope.seal -> task_envelopes; wait for a human `governor approve`
  |                authorize.consume(AUTHORIZE_L2) -> governor_approval_uses(fence)
  +- BUILDING      worktree(base) -> add the test only -> RED_PROOF eval
  |                -> add the smallest fix -> diff -> V1..V6 on the diff -> patch to vault
  +- TESTING       BASELINE, CANDIDATE, RERUN, ROLLBACK_REHEARSAL -> governor_evaluations
  +- REVIEWING     review.open_gate(bundle) -> independent reviewer -> review_decisions
  +- CANARYING     human AUTHORIZE_L3_CANARY -> CANARY eval on the synthetic corpus
  +- DECIDING      all gates -> ACCEPTED | REJECTED | BLOCKED
  +- LEARNING      learning.candidate(cycle facts) -> learning_records(candidate)
  +- CLOSED        receipts.build -> vault -> derived_artifacts -> cycle_receipts
                   -> governor_cycles(terminal) -> audit + outbox -> lease.release -> teardown
```

## 11. Critical details

- **Errors.** Every stage is wrapped. An exception marks the stage task
  failed, records `error_code` in `task_attempts`, and routes to LEARNING
  with BLOCKED (infrastructure) or REJECTED (candidate defect). On restart,
  `tick()` finds the open cycle and resumes from its task state. A crashed
  worker's late writes fail the fence check.
- **Idempotency.** Stage task keys are `sha256(cycle_key:stage:envelope_hash)`.
  Re-running an evaluation after a crash appends a `RERUN` row; it never
  overwrites one.
- **Reproducibility.** The candidate suite runs twice. Both runs must have
  the same counts and `outcome_set_hash`, which is `content_hash(sorted(node
  ids of every failed, errored, xfailed, or skipped node))`. Equal pass counts
  alone are not enough: during earlier pre-verification, an optional
  dependency appeared mid-session and moved tests from skipped to passed.
  `env_manifest_hash` covers the Python version, SQLite version, and installed
  test packages.
- **Baseline must be green.** If the base suite is not green in the sandbox
  (for example, a missing test dependency), the cycle is BLOCKED. It never
  reasons about "pre-existing failures". The repository has no
  `requirements-test.txt`; CI installs `flake8 pytest` plus
  `requirements.txt`. The sandbox mirrors CI, and adding a pinned test
  requirements file is a human task, because it is V6-protected.
- **Sandbox environment.** Built from `env_allowlist` only; every other
  variable is dropped. Git runs with `GIT_TERMINAL_PROMPT=0` and the worktree
  is detached. Network isolation is best effort locally; tests must not need
  the network.
- **Security.** V5 scans the diff, junit reports, the review bundle, and the
  receipt before any vault write, including `_AI_*` paths (section 3).
- **Performance.** One cycle per scope. The full suite runs in about 2
  seconds on the current tree. No queue or concurrency is needed.
- **Testing the governor.** `IMPLEMENTATION_DELTA.md` section 4 lists the
  tests: every schema trigger, veto unit tests, ranker determinism, the lease
  race, crash and resume, receipt-chain tamper detection, and an end-to-end
  synthetic cycle in a throwaway git repository under `tmp_path`.
