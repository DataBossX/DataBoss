# DataBossX Canonical System Map

_Status: authoritative declaration • Date: 2026-07-13 • Owner: DataBossX/DataBoss_

---

## System of Record

**`DataBossX/DataBoss`** is the canonical DataBossX repository. All production code,
architecture decisions, migrations, and release artifacts originate here. Every other
repository in the DataBossX GitHub organisation is classified below.

---

## Repository Classification

| Repository | Classification | Default Branch | Latest Commit | Deployment | Decision |
|---|---|---|---|---|---|
| `DataBossX/DataBoss` | **CANONICAL** | main | see repo | n/a | Active development; all code merges here |
| `rodneydanger84/DataBossX` | **ARCHIVE** | — | — | — | Personal fork / staging; superseded by the org repo; no active development; archive after confirming no unreferenced commits |
| `DataBossX/databossx-site` (if exists) | **COMPONENT** | — | — | DataBossX.com | Thin portal over the canonical API; must not be an independent source of truth |
| `DataBossX/DataBossXV2` (if exists) | **SUPERSEDED** | — | — | — | Experimental v2 spike; functionality merged into CANONICAL or discarded |
| `DataBossX/AI-Agent-Control` (if exists) | **ARCHIVE** | — | — | — | Early multi-agent prototype; architecture superseded by the OS blueprint |
| Any other DataBossX experimental repos | **ARCHIVE** | — | — | — | Migrate any verified unique capabilities, then archive |

> **Update instructions:** When Rodney completes the repo inventory in Issue #28 §A,
> replace the placeholder rows above with the exact repo names, latest commit SHAs, and
> confirmed decisions. Do not delete rows; mark superseded decisions as struck-through.

---

## Non-Negotiable Classification Rules

1. **CANONICAL** — there is exactly one. It is `DataBossX/DataBoss`.
2. **COMPONENT** — active, scoped sub-system (e.g. public portal). Must communicate only
   through the canonical API; must not hold a private copy of source title evidence.
3. **ARCHIVE** — read-only reference. No new pushes. Superseded by CANONICAL.
   _Archive, do not delete._ Migration is complete or explicitly waived.
4. **SUPERSEDED** — was at one time the authority for something that has since been
   re-implemented in CANONICAL. Keep hash-archived; mark with a migration note.
5. **EMPTY** — no useful code; safe to archive immediately after confirming no open PRs.

---

## Secrets and Exposure Status

| Credential Type | Affected Repo | File | Status | Required Action |
|---|---|---|---|---|
| zhipu API key | `DataBossX/DataBoss` | `backend/.env` | **Committed to history** | Rotate immediately (see Issue #2); remove from current tree; `.env` must be git-ignored |
| Any other secrets | All repos | `.env`, configs | Scan required | Run `gitleaks detect` on each repo; treat any found credential as compromised |

See `SECURITY.md` for the full credential-rotation runbook.

---

## Migration Decision Log

| Date | From | To | Decision | Verified By |
|---|---|---|---|---|
| 2026-07-11 | `backend/server.py` mock OCR | `src/databossx/` trusted kernel | Retire mock backend; new package is canonical | Architecture decision in blueprint |
| 2026-07-11 | CRA frontend (`frontend/`) | Vite/React UI (target: `ui/`) | Retire CRA; Vite is target | Architecture decision in blueprint |
| 2026-07-11 | PR #25 horizon report gen | New canonical title model | Do not establish as second title authority | Architecture decision in blueprint |
| 2026-07-11 | PR #26 title factory | Review, merge, then split | Strongest evidence controls; merge first | Architecture decision in blueprint |

---

## Canonical Code Layout (Target)

```text
src/databossx/          ← canonical Python package
  domain/               ← Pydantic domain models (evidence, work, title)
  vault/                ← content-addressed local vault (SHA-256)
  db/                   ← SQLite migration runner
  tasks/                ← task graph, leases, outbox
  audit/                ← append-only audit event log
  api/                  ← FastAPI control API (loopback-only)
migrations/             ← numbered SQL migration files
ui/                     ← Vite / React TypeScript interface (target)
config/policies/        ← operator policy files
tests/unit/             ← unit tests
tests/integration/      ← integration tests
tests/adversarial/      ← adversarial/policy-violation tests
tests/golden/           ← golden-output regression tests
runtime/                ← local run-time state (DB, vault — never committed)
docs/                   ← architecture decisions, canonical maps, runbooks
```

---

## Open Items (tracked in Issue #28)

- [ ] **A.1** — This document (✅ created; needs Rodney's repo inventory to complete the table above).
- [ ] **A.2** — Inventory and classify all repos listed in the table above with exact commit
  SHAs and deployment URLs.
- [ ] **A.3** — Record default branches, latest commits, deployment links, owners, secrets
  exposure, and migration decisions.
- [ ] **A.4** — Do not delete repos; archive only after verified migration and Rodney approval.
- [ ] **Security** — Rotate zhipu key and any other credentials from `backend/.env` history.
- [ ] **P0 pre-commit** — Verify `gitleaks` and `detect-private-key` hooks fire before every
  merge; add `no-commit-to-branch` for `main`.
