# ADR-0003 — SQLite now, PostgreSQL as the canonical cloud target

- Status: **Accepted** (explicitly provisional)
- Date: 2026-08-01 · Cycle `DBX-CC-10000X-20260801-001`

## Context

The directive names PostgreSQL as the owner of cloud workflow state. No database
service is reachable from this build environment and no client driver can be
installed (`psycopg` requires PyPI). The single-writer invariant is the most
important thing in this system, so it must be *executably* proven, not asserted.

## Decision

Implement the kernel against SQLite in WAL mode using **only the portable SQL
subset**, so the same DDL and the same tests carry to PostgreSQL.

Portable constructs used:

| Construct | SQLite | PostgreSQL |
| --- | --- | --- |
| Partial unique index (`WHERE state='ACTIVE'`) | supported | supported |
| `CHECK` constraints | supported | supported |
| Foreign keys | supported (`PRAGMA foreign_keys=ON`) | supported |
| Explicit `BEGIN IMMEDIATE` transactions | supported | `BEGIN` + row locks |
| Compare-and-swap `UPDATE ... WHERE consumed_at IS NULL` | supported | supported |
| Monotonic counter table | supported | supported (or a sequence) |

Deliberately avoided: `AUTOINCREMENT` semantics in logic, SQLite date functions,
`INSERT OR REPLACE`, and type affinity tricks. Timestamps are RFC 3339 strings
produced by `canonical.iso()`, identical on both engines.

## Non-portable items requiring translation

| SQLite | PostgreSQL equivalent |
| --- | --- |
| `CREATE TRIGGER ... RAISE(ABORT, 'X')` (holds, audit, accepted artifacts) | `CREATE FUNCTION` + `RAISE EXCEPTION` in a `BEFORE` trigger |
| `PRAGMA journal_mode=WAL` / `synchronous=FULL` | WAL is default; use `synchronous_commit=on` |
| `sqlite3.IntegrityError` | `psycopg.errors.UniqueViolation` — one mapping point in `kernel.claim_lease` |

## Consequences

- The invariant is proven now: twelve concurrent connections, exactly one lease.
- Migration is a translation of five triggers and one exception mapping, not a
  redesign.
- **This blocks private-canary readiness.** Recorded as open gap C-2 in
  `CURRENT_GAP_REPORT.md`. Canary requires re-running the same invariant tests
  against a real Postgres instance.

## Also decided

Local SQLite remains correct permanently for the runner's cache and durable
outbox, per the directive. Only the *cloud control state* moves to Postgres.
