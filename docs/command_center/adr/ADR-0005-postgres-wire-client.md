# ADR-0005 — A standard-library PostgreSQL wire client

- Status: **Accepted**
- Date: 2026-08-01 · Cycle `DBX-CC-10000X-20260801-001`
- Supersedes the provisional half of ADR-0003

## Context

ADR-0003 recorded SQLite as the executable engine and PostgreSQL as the
canonical target, with the gap listed as **blocking private-canary readiness**.
That was the single highest-severity open item: the one-writer invariant is the
most important property in this system, and it was proven only on the engine
that will not hold it in production.

Re-checking the environment turned up something the first pass had missed:
**PostgreSQL 16.13 is installed locally** (`/usr/lib/postgresql/16`). What was
missing was a *driver* — `psycopg2` needs PyPI, which is unreachable.

So the blocker was never "no PostgreSQL." It was "no client library."

## Decision

Write the client. `services/control_api/command_center/pg_wire.py` implements
the PostgreSQL v3 frontend/backend protocol over a plain socket:

- startup and parameter negotiation, including `search_path` pinning;
- authentication: trust, cleartext, md5, and SASL SCRAM-SHA-256;
- the **extended query protocol** (Parse → Bind → Describe → Execute → Sync);
- typed result decoding by column OID;
- `CommandComplete` row counts, which the compare-and-swap paths depend on;
- `ErrorResponse` decoding that preserves SQLSTATE, so `23xxx` becomes an
  integrity error and `P0001` becomes a trigger refusal.

**Parameters are bound by the server, never interpolated into SQL text.** That
is why the extended protocol was worth implementing instead of the much simpler
simple-query protocol with client-side quoting: hand-rolled escaping is exactly
the kind of thing that looks fine until it is a vulnerability.
`test_parameters_are_bound_not_interpolated` fires a classic injection payload
through a bound parameter and asserts it comes back as literal text with all
four holds intact.

`db.py` now carries both dialects: one shared set of table and index DDL, and
two trigger sets, because triggers are the one place the dialects genuinely
diverge (`RAISE(ABORT, …)` versus a plpgsql function raising `P0001`).

## Consequences

**Positive**

- The invariant is proven where it counts: all **169 tests pass against real
  PostgreSQL 16.13**, including the twelve-thread lease race and the full
  vertical slice.
- Verification is local and repeatable, not deferred to a future environment.
- The zero-dependency posture of ADR-0001 is preserved end to end.
- CI runs the identical suite against a `postgres:16` service container, so the
  result is reproduced independently of this machine.

**Negative**

- A hand-written protocol client is code we now own. Scope is kept deliberately
  small — no COPY, no cursors, no binary formats, no async — and each omission
  is one the kernel does not use.
- It is not a general-purpose driver and should not be presented as one.

## What running against PostgreSQL actually caught

Two real portability defects that SQLite had been hiding:

1. **`HAVING n > 1`** in `SecurityWatcher` referenced a `SELECT` alias. SQLite
   accepts it; PostgreSQL rejects it (`42703`). The duplicate-active-lease check
   — a *security* check — would have failed on the canonical engine. Now
   `HAVING COUNT(*) > 1`.
2. **`DROP TRIGGER`** without a table name in the audit-tamper test. PostgreSQL
   requires `ON <table>`.

Both were invisible on SQLite. That is the argument for this ADR in one line.

## Migration note

`psycopg2` remains the right choice for a production deployment that can install
it. `db.connect()` dispatches on the DSN, so swapping the client is a change in
one function; the kernel, the schema, and the tests are untouched by it.
