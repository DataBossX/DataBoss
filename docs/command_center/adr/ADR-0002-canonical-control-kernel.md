# ADR-0002 — Python is the single canonical control kernel

- Status: **Accepted**
- Date: 2026-08-01 · Cycle `DBX-CC-10000X-20260801-001`

## Context

The baseline carried two candidate control planes:

1. Node/Express + SQLite prototypes (and a CRA frontend under `frontend/`),
2. Python `src/databossx` — models, database, immutable intake, content-addressed
   hashing, orchestrator.

The directive is explicit: *"Do not preserve both a Node and Python backend as
competing canonical control kernels."* Two mutable owners of the same fact is
the failure mode that produces unresolvable disagreements about what is true.

## Decision

**Python owns the control kernel.** The web tier is a pure client with no
authority.

Evidence for Python over Node:

| Criterion | Python `src/databossx` | Node prototypes |
| --- | --- | --- |
| Exact title arithmetic | `Fraction`/`Decimal` already used throughout `horizon/` | JS numbers are IEEE-754 doubles; unsuitable as ownership authority |
| Immutable intake + content addressing | Present and tested | Absent |
| Reuse of tested domain code | Direct | Would require reimplementation |
| Security posture at baseline | Clean | `backend/server.py` ships `allow_origins=["*"]` |
| Runs in this environment | Yes (stdlib) | Yes, but no npm packages installable |

The floating-point point is decisive on its own: the directive forbids binary
floating point as the title ownership authority.

## Consequences

- `services/control_api/command_center/` is the only writer of control state.
- `backend/` and `frontend/` are **not** adopted. They are untouched this cycle
  (outside the write scope) and remain scheduled for retirement per
  `docs/DATABOSSX_OS_BLUEPRINT.md`.
- `mineral_deal_room/` contributes UI patterns only, never authority.
- The PWA holds no risk logic: it cannot classify, approve, lease, or clear a
  hold. Every such decision is a server round-trip.

## Deprecations recorded, not executed

Nothing was deleted. The directive forbids deleting legacy branches, files, or
evidence as cleanup. Retirement of `backend/` and `frontend/` requires its own
authorized lane.
