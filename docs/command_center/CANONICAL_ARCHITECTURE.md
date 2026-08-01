# CANONICAL ARCHITECTURE — DataBossX Command Center

Release state: **FOR REVIEW — HOLD — NO EXTERNAL RELEASE**
Cycle: `DBX-CC-10000X-20260801-001` · Baseline `582d951`

## 1. Division of responsibility

| System | Owns | Never owns |
| --- | --- | --- |
| **GitHub** (`DataBossX/DataBoss`) | Code, schemas, migrations, policy, CI, tests, build provenance | Runtime workflow state; client evidence |
| **Control kernel DB** | Commands, jobs, approvals, leases, fencing sequences, audit, outbox, holds, artifact index | Raw evidence bytes; human decision records |
| **Google Drive** | Human-readable commands, accepted artifacts, immutable snapshots, receipts, decision records | Transactional state; anything that must be atomic |
| **Local Windows runner** | Local files, raw title evidence, Excel, local models, bounded execution | Cloud authority; inbound connections |
| **Phone PWA** | Interaction, requests, approvals, status, read-only evidence navigation | Shell access, file browsing, raw evidence storage, risk decisions |

**No fact has two mutable owners.** Cross-system links use stable IDs
(`command_id`, `task_id`, `receipt_id`, `logical_id`), never duplicated values.

## 2. Repository layout added this cycle

```
apps/control-center-web/          Phone PWA (zero dependencies, installable)
  index.html  static/app.css  static/app.js  sw.js  manifest.webmanifest  icons/
services/control_api/command_center/
  __init__.py      canonical.py    errors.py      state_machines.py
  policy.py        db.py           kernel.py      voice.py
  best_moves.py    watchers.py     drive_bridge.py runner.py
  http_api.py      slice.py        pg_wire.py
packages/contracts/               5 JSON Schema contracts
tests/command_center/             169 tests (SQLite + PostgreSQL) + legacy runner
scripts/                          cdp_client.py, command_center_visual_qa.py
docs/command_center/              this set, plus ADRs
evidence/command_center/          screenshots and QA report
```

## 3. Control flow

```
voice / text
   → transcript (hashed, audio discarded)
   → parsed intent (separate object; unknowns listed, never guessed)
   → HUMAN CONFIRMS BOTH
   → CommandEnvelope (immutable, idempotency-keyed, content-hashed)
   → deterministic policy classification
        READ_ONLY | SIMULATION | APPROVAL_REQUIRED | PROHIBITED
   → Best Moves ranking (score) + veto set (removal, not subtraction)
   → [APPROVAL_REQUIRED] step-up + single-use ApprovalToken bound to
     actor, operation, scope, parameter hash, envelope hash, input hashes,
     policy version, nonce, expiry
   → WriterLease claim (one per scope) + monotonic fencing sequence
   → TaskEnvelope (adapter allowlist only; no path, no shell, no SQL)
   → WriterACK (binds envelope hash + lease hash)
   → runner re-verifies EVERYTHING, then executes
   → VerificationReceipt (hashes, checks, holds, SIMULATED label)
   → Drive publish: stage → hash → upload → READ BACK → compare → advance pointer
   → watchers review read-only and issue ReviewReceipts
```

## 4. The single-writer invariant

Enforced by the database, not by application state:

| Mechanism | Location | What it stops |
| --- | --- | --- |
| `ux_lease_one_active_per_scope` (partial unique index) | `db.py` | Two ACTIVE leases on one scope |
| `fencing_counters` + in-transaction increment | `kernel.claim_lease` | Sequence reuse or regression |
| `assert_fencing_current` | `kernel`, `runner` | A stale writer mutating anything |
| `ux_lease_scope_sequence` | `db.py` | Duplicate sequence rows |
| Heartbeat + stale threshold | `_expire_stale_leases` | A dead writer holding a scope forever |

Proven by `test_concurrent_claims_produce_exactly_one_winner`: twelve threads,
twelve independent connections, one winner and eleven `LEASE_HELD` — **on both
SQLite and PostgreSQL 16.13**. The same partial unique index carries the
guarantee on each engine (ADR-0005).

## 5. Atomicity

Every state change and its audit event share one transaction. Audit events are
hash-chained (`prev_sha256` folded into `content_sha256`) and the table is
append-only via triggers. Failure-injection tests prove that when the audit
write fails, the state change is rolled back with it.

## 6. Simulated vs real

| Layer | Where the label appears |
| --- | --- |
| Database | `task_envelopes.execution_mode`, receipt payload |
| API | `execution_mode` on every receipt and posture entry |
| Audit | `TASK_ENVELOPE_ISSUED` and `RECEIPT_RECORDED` detail |
| Artifact bytes | `"SIMULATED": true` inside every generated artifact |
| Receipt prose | `plain_language_result` begins `[SIMULATED]` |
| UI | Persistent `SIMULATED` pill plus per-item mode badges |

`NoFabricationWatcher` fails the review if a SIMULATED receipt's prose omits the
label. The runner is configured `simulation_only=True` and refuses `REAL`.

## 7. Deviations from the directive's preferred stack, with reasons

| Directive preference | Built | Why |
| --- | --- | --- |
| React + Vite + Tailwind PWA | Hand-written HTML/CSS/JS PWA | npm registry returns HTTP 403 (network policy). A build that cannot install cannot be tested. See ADR-0001. |
| PostgreSQL canonical store | **Both.** PostgreSQL 16.13 verified; SQLite retained for the runner cache and offline work | A stdlib wire client (ADR-0005) removed the blocker. 169/169 tests pass on PostgreSQL; the same DDL drives both engines. |
| Python API via FastAPI | `http.server` stdlib API | FastAPI not installable. Same security controls, implemented explicitly. |
| `pytest` suite | `unittest` suite | `pytest` not installable; a suite that cannot run cannot be reported as passing. |
| Real speech provider | `SpeechProvider` port + local stub | Paid service; spending requires the owner's approval. |

Every deviation is a network-policy consequence, not a design preference, and
each leaves a named seam for the preferred technology.

## 8. Donor decisions

- **Canonical control kernel: Python.** The baseline carried two candidate
  kernels; the directive forbids keeping both. See ADR-0002.
- `src/databossx` — preferred donor, **unmodified**. Patterns reused
  (content addressing, versioned assets, WAL); no competing ownership.
- `horizon/` — preserved untouched; Section 32 hold honoured.
- `backend/` — **not adopted** as a control plane. Its wildcard CORS was fixed
  in place under the owner's "do all best moves" instruction (exact origin
  allowlist; a wildcard now disables credentials). It still carries mock OCR and
  remains scheduled for retirement per the blueprint.
- `website/` — untouched; marketing stays separate from the control plane.
