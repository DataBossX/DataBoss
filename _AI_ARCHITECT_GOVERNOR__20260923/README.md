# DataBossX Continuous Improvement Governor: architecture packet (2026-09-23)

**Status: DESIGN ONLY. DO NOT MERGE THIS FOLDER AS RUNTIME. DO NOT IMPORT IT.**

This folder is an isolated, public-safe architecture proposal for Issue
[#68](https://github.com/DataBossX/DataBoss/issues/68) (Continuous Improvement
Governor) and its Phase 0 child [#69](https://github.com/DataBossX/DataBoss/issues/69).
It contains Markdown only. Nothing here is executable, nothing here is on any
import path, and nothing here should be copied wholesale into `src/`.

## What this packet is

A blueprint that **extends the governor v0 already on branch
`cursor/kernel-governor-tournament-7f1f`** (`src/databossx/governor/`,
`migrations/002_governor.sql`) instead of adding a second one. The governor
reuses the existing per-project SQLite database, `runs`, `tasks`,
`task_leases`, `approvals`, `audit_events`, `outbox_events`,
`derived_artifacts`, and the content-addressed vault. It keeps v0's six
table names, hardens them with constraints and triggers, and adds six
`governor_*` tables for records nothing else can hold.

It is **not**:

- a second OS, orchestrator, queue, ledger, approval store, policy engine, or
  agent platform;
- a `gov_*` or `cb_*` table family beside v0 (parked PR #67 is the
  counter-example);
- a replacement for the trusted kernel drafted in PR
  [#114](https://github.com/DataBossX/DataBoss/pull/114). The governor uses
  that kernel's runner, task transitions, policy engine, and review gates at
  their canonical paths, carried over byte-identical, never copied under
  `governor/`;
- a runtime to merge from the challenger folder in PR
  [#116](https://github.com/DataBossX/DataBoss/pull/116). That folder, like
  this one, is advisory text only.

## Files

| File | Purpose |
| --- | --- |
| `ARCHITECTURE.md` | Decision, reuse map, v0 disposition, components, the revised `002_governor.sql` (verified), state machines, ranking, receipts |
| `TASK_ENVELOPE.md` | Task envelope v2 fields, canonical hashing, hard vetoes V1 to V6, blocking gates |
| `FIRST_CYCLE.md` | The exact first synthetic cycle on `5fc0d6c`: detect the missing negated-marker regression under Issue #94 regression 4, add the smallest test and a one-line fix, and receipt it. Appendix A gives the PR #114 variant |
| `IMPLEMENTATION_DELTA.md` | Prerequisites, then the concrete files the parent writer revises or creates under `src/databossx/governor/`, `migrations/`, `config/governor/`, and `tests/` |
| `RECEIPT.md` | Terminal receipt for this architecture task: inputs, verifications, findings, hashes, safety flags |

## Isolation rules for this folder

1. Markdown only. No `.py`, `.sql`, `.json`, or `.toml` file lives here, so
   no test runner, migration runner, or packager can pick anything up.
2. SQL, JSON, and Python in these documents are specifications. The parent
   writer re-creates them at the canonical paths in `IMPLEMENTATION_DELTA.md`,
   under normal review. The SQL block in `ARCHITECTURE.md` carries its
   SHA-256, so a faithful copy can be checked.
3. No client facts, private paths, Drive identifiers, private hashes,
   credentials, or workbook content appear here. Every fixture is marked
   `SYNTHETIC TEST DOCUMENT -- NOT REAL TITLE DATA`. The only hashes quoted
   are of public repository files, public commits, and synthetic artifacts.
4. Nothing here authorizes merge, deployment, client evidence access,
   workbook mutation, hold removal, external release, purchases, or
   destructive cleanup. All existing holds remain active.
5. Note for reviewers: the branch's publication gate currently skips every
   `_AI_*` path (`policy_gate.py:40`), so CI does not scan this folder. This
   packet was scanned separately with the same patterns (see `RECEIPT.md`),
   and `IMPLEMENTATION_DELTA.md` item 0.5 closes the gap.

## Disposition (Issue #69 vocabulary)

| Item | Disposition |
| --- | --- |
| This folder | `PRESERVE_AS_TEST_OR_REFERENCE` (design reference only) |
| Governor v0 on this branch | `CANONICALIZE_NOW` after the revisions in `IMPLEMENTATION_DELTA.md`; `cycle.py`'s demo is `SUPERSEDE_AFTER_PROOF` |
| Revised `migrations/002_governor.sql` | `CANONICALIZE_NOW` (replaces v0's file before first merge to `main`) |
| PR #114 runner, `tasks.py`, `policy.py`, `002_kernel_and_connectors.sql` | `PORT_AS_BOUNDED_SLICE`, byte-identical from `e8b9225`, plus one separate deny-unknown policy fix |
| Issue #94 implementations (this branch versus PR #114) | owner decision; the other becomes `SUPERSEDE_AFTER_PROOF` |
| PR #116 challenger folder | `PRESERVE_AS_TEST_OR_REFERENCE`; never runtime |
| Parked PR #67 `cb_*` tables and parallel receipts and audit | `REJECT` as runtime |

`FOR REVIEW - HOLD NO EXTERNAL RELEASE`
