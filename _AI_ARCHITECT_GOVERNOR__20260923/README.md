# DataBossX Continuous Improvement Governor: architecture packet (2026-09-23)

**Status: DESIGN ONLY. DO NOT MERGE THIS FOLDER AS RUNTIME. DO NOT IMPORT IT.**

This folder is an isolated, public-safe architecture proposal for Issue
[#68](https://github.com/DataBossX/DataBoss/issues/68) (Continuous Improvement
Governor) and its Phase 0 child [#69](https://github.com/DataBossX/DataBoss/issues/69).
It contains Markdown only. Nothing here is executable, nothing here is on any
import path, and nothing here should be copied wholesale into `src/`.

## What this packet is

A blueprint for **one governor module** that lives inside the existing
`src/databossx` package, as `src/databossx/governor/`. It reuses the existing
per-project SQLite database, `runs`/`tasks`/`task_leases`, `approvals`,
`audit_events`, `outbox_events`, `derived_artifacts`, and the content-addressed
vault. It adds only governor-specific records in `gov_*` tables.

It is **not**:

- a second OS, orchestrator, queue, ledger, approval store, policy engine, or
  agent platform;
- a replacement for the trusted kernel drafted in PR
  [#114](https://github.com/DataBossX/DataBoss/pull/114). The governor depends
  on that kernel (task transitions, policy engine, migration runner,
  review gates) and must land after it;
- a runtime to merge from the challenger folder in PR
  [#116](https://github.com/DataBossX/DataBoss/pull/116). That folder, like this
  one, is advisory text only.

## Files

| File | Purpose |
| --- | --- |
| `ARCHITECTURE.md` | Components, reuse map, `gov_*` tables (proposed migration), state machines, receipts |
| `TASK_ENVELOPE.md` | `TaskEnvelope.v2` fields, canonical hashing rule, hard vetoes, blocking gates |
| `FIRST_CYCLE.md` | The exact first synthetic cycle: detect the missing Issue #94 regression, add the smallest test and fix, emit a receipt |
| `IMPLEMENTATION_DELTA.md` | Concrete files the parent writer should create or modify under `src/databossx/governor/`, `migrations/`, `tests/`, `config/` |
| `RECEIPT.md` | Terminal receipt for this architecture task: what was read, what was verified, hashes, safety flags |

## Isolation rules for this folder

1. Markdown only. No `.py`, `.sql`, `.json`, or `.toml` file lives here, so no
   test runner, migration runner, or packager can pick anything up.
2. SQL, JSON, and Python in these documents are specifications. The parent
   writer re-creates them in their canonical locations listed in
   `IMPLEMENTATION_DELTA.md`, under normal review.
3. No client facts, private paths, Drive identifiers, private hashes,
   credentials, or workbook content appear here. All fixtures are marked
   `SYNTHETIC TEST DOCUMENT -- NOT REAL TITLE DATA`. The only hashes quoted
   are of public repository files and of synthetic artifacts.
4. Nothing here authorizes merge, deployment, client evidence access, workbook
   mutation, hold removal, external release, purchases, or destructive cleanup.
   All existing holds remain active.

## Disposition (Issue #69 vocabulary)

| Item | Disposition |
| --- | --- |
| This folder | `PRESERVE_AS_TEST_OR_REFERENCE` (design reference only) |
| Proposed `src/databossx/governor/` | `PORT_AS_BOUNDED_SLICE` after PR #114 lands |
| Proposed `gov_*` migration | `PORT_AS_BOUNDED_SLICE`; numbered after PR #114's `002` |
| PR #116 challenger folder | `PRESERVE_AS_TEST_OR_REFERENCE`; never runtime |
| Parked PR #67 `cb_*` tables / parallel receipts and audit | `REJECT` as runtime (duplicate audit/approval/lease stores) |

`FOR REVIEW - HOLD NO EXTERNAL RELEASE`
