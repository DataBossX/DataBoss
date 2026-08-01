# CURRENT GAP REPORT — DataBossX Command Center 10000X

Baseline: `582d95161cf8220fb37f5224e21e57dcc5c3121c` · Cycle `DBX-CC-10000X-20260801-001`
Release state: **FOR REVIEW — HOLD — NO EXTERNAL RELEASE**

## A. What already exists (donor inventory)

| Surface | Assessment | Disposition this cycle |
| --- | --- | --- |
| `src/databossx/` (Python: models, database, intake, hashing, orchestrator, api, config) | Strongest control-adjacent donor. Content-addressed vault, immutable intake, SQLite schema, project/asset versioning. Imports cleanly under stdlib. | **Preferred donor.** Not modified. Command Center reuses its *patterns* (content addressing, versioned assets, WAL) and coexists without competing for the same facts. |
| `horizon/` (exact `Fraction` title math, chaining, controlled loop, audit, artifacts) | Mature, hold-aware, no-fabrication behavior already encoded. | **Preserved untouched.** Section 32 hold honored. |
| `backend/server.py` (FastAPI) | **Security defect: `allow_origins=["*"]`** (wildcard CORS) plus mock OCR. Blueprint already marks it for retirement. | **Not adopted as control plane.** Not modified (out of write scope). Recorded as an open defect below. |
| `frontend/` (CRA + Tailwind) | Legacy prototype, no control-plane semantics. | Not adopted, not modified. |
| `website/` (Astro cinematic marketing site + `ReleaseGate.astro`) | Marketing surface. Directive requires marketing stay separate from the private control plane. | Left alone; Command Center is a separate app under `apps/control-center-web/`. |
| `mineral_deal_room/` (Vite UI shell) | UI patterns only, static sample data. | Not adopted this cycle. |
| `src/databossx/api.py` | Requires FastAPI, which cannot be installed here. | Not used; stdlib HTTP API built instead. |

## B. Gaps closed by this cycle

| # | Gap at baseline | Closed by |
| --- | --- | --- |
| 1 | No writer lease, fencing token, or single-writer invariant anywhere in repo | `services/control_api/command_center/kernel.py` + DB constraints |
| 2 | No TaskEnvelope / WriterACK / ApprovalToken concepts | `kernel.py`, `packages/contracts/*.json` |
| 3 | No deterministic policy classifier (READ_ONLY / SIMULATION / APPROVAL_REQUIRED / PROHIBITED) | `policy.py` |
| 4 | No validated state machines; states were implicit strings | `state_machines.py` + DB-layer transition rejection |
| 5 | No audit/outbox atomicity guarantee | single-transaction writes in `kernel.py`, proven by failure-injection test |
| 6 | No machine-enforced holds; holds were prose in Markdown | `holds` table + `HoldRemovalForbidden`, unremovable by API, UI, model, watcher, or writer |
| 7 | No mobile PWA, no installability, no six-question executive view | `apps/control-center-web/` |
| 8 | No voice intake pipeline or transcript/intent separation | `voice.py` + two-step confirmation in the PWA |
| 9 | No Best Moves ranking or explainability | `best_moves.py` with transparent weighted factors |
| 10 | No watcher roles; nothing distinguishes reviewers from writers | `watchers.py`, read-only by construction |
| 11 | No Drive bridge with hash + readback verification | `drive_bridge.py` (staging → hash → upload → readback → manifest pointer) |
| 12 | No outbound-only runner with allowlist and fencing enforcement | `runner.py` |
| 13 | No idempotency on duplicate command / double tap | idempotency keys, unique index, proven by test |
| 14 | No red-team suite | `tests/command_center/test_red_team.py` (34 scenarios) |
| 15 | No simulated-vs-real labeling discipline | `SIMULATED` propagated through API, DB, receipt, and UI |

## C. Gaps that remain OPEN after this cycle

| # | Open gap | Severity | Why it remains | Owner action needed |
| --- | --- | --- | --- | --- |
| 1 | ~~Legacy `pytest` suite cannot execute~~ **CLOSED** | resolved | GitHub Actions ran it: `303 passed, 7 skipped` (run 30686563726, commit `8ef49c1`) | none — done |
| 2 | PostgreSQL not available; kernel runs on SQLite | **BLOCKS CANARY** | No network/service; directive names Postgres as canonical cloud store | Provision Postgres; run the same migrations (DDL kept portable) and re-run invariant tests |
| 3 | Real Drive writes not performed | HIGH | No active authorization; `00_AUTHORIZATION_REQUEST...NOT_YET_ACTIVE` confers nothing | Activate authorization, then run the Drive bridge against the verified parent |
| 4 | `03_RECEIPTS` vs existing `receipts` folder conflict unresolved | MEDIUM | Directive forbids creating/moving Drive folders without verified authority | Owner decides: rename, alias, or adopt existing `receipts` |
| 5 | `backend/server.py` wildcard CORS with FastAPI | HIGH (pre-existing) | Outside this lane's write scope | Authorize a scoped fix lane, or retire `backend/` per blueprint |
| 6 | Reported commits `0940799`, `517d515`, `faae97a` unreachable | MEDIUM | Live only in unpushed `C:\DataBoss\DataBossX` | Push that local state, or confirm it is abandoned |
| 7 | WebAuthn/passkey step-up is interface-only | MEDIUM | Requires a registered authenticator and HTTPS origin | Register credentials on the canary host |
| 8 | Real speech-to-text provider not wired | MEDIUM | Paid service; directive forbids spending without approval | Approve a provider; implement the existing `SpeechProvider` port |
| 9 | No signed release provenance / attestations | MEDIUM | Requires CI identity and release authority | Enable once a release lane is authorized |
| 10 | Title domain entities modeled but not populated | LOW | Deliberate — synthetic data only, no client evidence | Populate only inside the private boundary |

## D. Known pre-existing test conditions (recorded separately, not caused here)

- `tests/*.py` legacy suite: not runnable **in the build environment** (no PyPI),
  so it was never claimed as passing there. **CI has since run it under real
  pytest with all dependencies: `303 passed, 7 skipped`, zero failures.**
- `backend_test.py` requires FastAPI/httpx — unavailable, not run.
- `tests/test_grocery_pipeline.py` uses a module-scoped fixture and external
  spreadsheet dependencies — unsupported by the stdlib runner, reported SKIPPED-UNSUPPORTED.

## E. Architectural conflict resolved

The baseline carried **two candidate control kernels** (Node/Express+SQLite in
prototypes, and Python `src/databossx`). The directive forbids keeping both as
competing canonical kernels. **Decision: Python is the canonical control
kernel**; the web tier is a pure client. Recorded in
`docs/command_center/adr/ADR-0002-canonical-control-kernel.md`.
