# Self-Improving Evolution Loop — design harness for DataBossX issue #68

Source issue: https://github.com/DataBossX/DataBoss/issues/68 ("Build the
DataBossX Continuous Improvement Governor")

Read first, in this order:

1. `docs/DATABOSSX_OS_BLUEPRINT.md` — "Self-builder, safely," "Task engine,"
   and "Model routing." That document is the actual architecture decision.
2. `src/databossx/orchestrator.py` — the real, single-writer task seeder.
3. `horizon/orchestrator.py` and `horizon/CONTROLLED_LOOP.md` — the two
   existing bounded loops in this repository (Ingest→Validate→Repair→
   Evaluate→Iterate, and Inspect→Plan→Execute→Verify→Score→Repair→Promote→
   Learn). Both are finite, both write only new versions, both stop instead
   of guessing when they cannot make progress.
4. This directory.

## What this is

A **design harness**: one small, stdlib-only Python module
(`evolution_loop.py`) plus tests and docs that demonstrate the cycle issue
#68 asks for:

```
OBSERVE -> PROPOSE -> PRIORITIZE -> AUTHORIZE (L2 sandbox only)
-> BUILD -> TEST -> ADVERSARIAL -> RECEIPT -> LEARN
```

on a **synthetic fixture** — a tiny invented "repo" with one covered and one
uncovered module. It never reads real proprietary content, never writes
outside a disposable sandbox/temp directory, and never merges, deploys, or
touches client evidence.

## What this is not

- **Not a second control plane.** It does not add a database, queue, lease
  manager, policy engine, or approval store that competes with the
  canonical kernel the blueprint describes (`docs/DATABOSSX_OS_BLUEPRINT.md`,
  "Target architecture") or with `horizon/orchestrator.py` /
  `horizon/controlled_loop.py`. If issue #68's canonical kernel (Phases 1–3)
  is ever built, the ranking/veto/receipt *logic* here is meant to be ported
  into it, not run alongside it.
- **Not production code.** Nothing in this directory is imported by
  `src/databossx`, `horizon`, or any application entry point. It is
  reviewable reference material.
- **Not a model caller.** `evolution_loop.py` never calls an LLM API. BUILD
  deterministically invents a trivial fixture (`add(a, b)`) and its test —
  it does not ask a model to write code. That keeps the whole cycle
  reproducible, offline, and safe to run in CI with no credentials.
- **Not an escalation path.** Nothing here can request or grant more than
  `AutonomyLevel.L2` (`MAX_AUTONOMY_LEVEL` in `evolution_loop.py`). There is
  no code path — not even a bug — that reaches L3/L4, because the ceiling is
  checked at proposal creation, at the hard-veto stage, and again inside
  `authorize()` itself (defense in depth, not "trust the caller").

## Files

| File | Purpose |
| --- | --- |
| `README.md` | This file: scope, contract, non-goals. |
| `evolution_loop.py` | The nine-stage cycle. Copy-ready, stdlib-first. |
| `test_evolution_loop.py` | 60 `unittest` cases; no network, no third-party deps. |
| `CI_HOOK.md` | A GitHub Actions job that runs OBSERVE+PROPOSE only, on every PR, with zero repo writes. |
| `LEARNING_MEMORY.md` | What may become durable `LearningRecord` knowledge vs. what is forbidden. |
| `RECEIPT.md` | The receipt schema, hash-chain rule, and terminal-state catalog. |

## The cycle contract

Every stage has an explicit input, output, and stop condition. None of them
guess when evidence is missing; they record why and halt.

| # | Stage | Input | Output | Hard stop conditions |
| - | --- | --- | --- | --- |
| 1 | **OBSERVE** | a root directory (metadata only — file names/paths, never contents) + `KNOWN_ISSUE_SEEDS` | `list[Observation]`, each cross-checked against the filesystem, plus a `baseline_hash` | none (an empty result is a valid, non-error outcome) |
| 2 | **PROPOSE** | `list[Observation]` | `list[ImprovementProposal]` (value/risk/cost/reversibility/confidence, all bounded `[0,1]`) | out-of-bounds fields are caught at PRIORITIZE, not silently clamped |
| 3 | **PRIORITIZE** | proposals + `PrioritizeContext` (current baseline hash, budget ceiling, reversibility floor, ledger of already-terminal proposal IDs) | `list[PrioritizedProposal]`, sorted eligible-first then by deterministic score | any of the 8 `HARD_VETOES` (see below) marks a proposal permanently ineligible **for this cycle's ledger state** |
| 4 | **AUTHORIZE** | the top eligible `PrioritizedProposal` + a sandbox root | a single-use, expiring `Authorization` at exactly `AutonomyLevel.L2` | requested autonomy above L2 → refuse; proposal not eligible → refuse (re-checked, not trusted from the caller) |
| 5 | **BUILD** | a hashable `TaskEnvelope` bound to the proposal+authorization hashes | a `BuildArtifact` (files + hashes, written only under `resolve_within(sandbox_root, ...)`) | envelope/authorization hash mismatch, expired authorization, or any write outside the sandbox (`SandboxEscape`) |
| 6 | **TEST** | `BuildArtifact` | `TestOutcome` from running the invented canary test via `python -m unittest` in a subprocess scoped to the sandbox `cwd` | non-zero exit or timeout → `REJECTED_BUILD_UNVERIFIABLE`, cycle ends |
| 7 | **ADVERSARIAL** | `BuildArtifact` + envelope + authorization | `AdversarialOutcome` from 5 control probes (path traversal, secret scan, injection resistance, permission-expansion, rollback rehearsal) | any probe failing → `REJECTED_ADVERSARIAL`, cycle ends |
| 8 | **RECEIPT** | every stage's hash + the terminal state | an append-only, hash-chained `Receipt` | if the ledger's existing chain fails verification, `append()` raises `AuditChainCompromised` instead of writing — the module **halts rather than repairs its own audit history** |
| 9 | **LEARN** | the receipt | a `LearningRecord`, `status="reviewed"` only if a human passed both `reviewed_by` and `review_note`; otherwise `status="quarantined"` | nothing this module wrote to itself is ever auto-marked reviewed |

## Autonomy boundaries enforced by this module

Matches issue #68's L0–L4 ladder. This module implements only L0–L2 and
refuses, by construction, to go further:

- **L0 Observe** — `observe()` reads names/paths only.
- **L1 Draft** — `propose()` / `compile_task_envelope()` produce data, no
  runtime mutation.
- **L2 Isolated implementation** — `build_synthetic_canary()` writes only
  inside a disposable sandbox directory; `_maybe_local_git_commit()` makes a
  local commit *inside that disposable directory's own throwaway `.git`*,
  never the real repository's history.
- **L3 Private canary** and **L4 External action/release** are not
  implemented here at all. `MAX_AUTONOMY_LEVEL = AutonomyLevel.L2_ISOLATED`
  is checked in three independent places (`propose()`'s
  `requested_autonomy`, the `_veto_autonomy_ceiling` hard veto, and
  `authorize()` itself) so a bug in any one of them does not silently raise
  the ceiling.

## Stop conditions (cycle-level)

Any one of these ends the current cycle immediately and is recorded in the
receipt's `terminal_state` — see `RECEIPT.md` for the full catalog:

1. `NO_ELIGIBLE_PROPOSAL` — OBSERVE found nothing, or nothing survived
   PRIORITIZE.
2. `VETOED` — a hard veto fired (forbidden category, stale baseline,
   over-budget, low reversibility, low confidence at high risk, duplicate,
   out-of-bounds field, or an autonomy request above L2).
3. `AUTHORIZATION_DENIED_SCOPE` — `authorize()` refused (should be
   unreachable if PRIORITIZE ran correctly; kept as a second gate).
4. `AUTHORIZATION_EXPIRED` — the TTL elapsed before BUILD started.
5. `REJECTED_SANDBOX_ESCAPE` — BUILD attempted a write outside its
   authorized root.
6. `REJECTED_BUILD_UNVERIFIABLE` — the invented canary test itself failed
   to pass.
7. `REJECTED_ADVERSARIAL` — a control probe caught a regression in the
   safety mechanisms.
8. `AUDIT_CHAIN_COMPROMISED` — the receipt ledger was found tampered;
   the module refuses to append and exits non-zero (`main()` returns `2`).
9. `PROMOTED_DRAFT_PR_ELIGIBLE` — every gate passed. This means exactly one
   thing: *a human or a separate CI step may now open a **draft** PR
   attaching this receipt as evidence.* It is not permission to merge,
   deploy, or touch anything outside the sandbox that already no longer
   exists (rollback rehearsal deletes it before the receipt is even
   written).

Cycle-level (not per-stage) stop conditions:

- **No internal repetition.** `run_cycle()` runs once. There is no
  `while True` anywhere in this module. "Automatically repeatable" means an
  external scheduler (CI on every push, cron, a human) invokes the script
  again — see `CI_HOOK.md`.
- **One cycle per scope at a time.** `SingleCycleLock` uses an atomic
  `O_CREAT|O_EXCL` file plus a monotonic fencing counter; a second concurrent
  invocation against the same `runtime_dir` raises `CycleAlreadyRunning`
  instead of racing.
- **Idempotency / no rework.** `_veto_duplicate_terminal` refuses to
  re-process a `proposal_id` that already has a terminal receipt in the
  ledger.

## Non-negotiables (unconditional, not scored)

Straight from the blueprint's "Non-negotiable rules" and issue #68's
"Explicit non-authority," each backed by a specific mechanism in this code:

| Rule | Mechanism |
| --- | --- |
| Never mutate client bytes | OBSERVE never reads file contents; BUILD never reads real repo files at all — it invents its own fixture |
| Never expand permissions | `TaskEnvelope.allowlist_write` is exactly `(sandbox_root,)`; probed every cycle by `_probe_permission_expansion` |
| Never edit audit history | `ReceiptLedger.append()` is `open(path, "a")` only, and refuses to append if the existing chain fails `verify_chain()` |
| Never auto-merge / auto-deploy | no such code path exists; `PROMOTED_DRAFT_PR_ELIGIBLE` is the highest terminal state and it only describes eligibility |
| No second control plane | no database, no queue, no daemon; one process, one finite run, stdlib only |
| Raw model claims ≠ knowledge | see `LEARNING_MEMORY.md`; `learn()` requires an explicit human `reviewed_by` + `review_note` |

## Running it

```bash
# Dry run: OBSERVE + PROPOSE only, zero filesystem writes, safe on any repo.
python3 evolution_loop.py --repo-root /path/to/repo --mode observe-propose

# Full cycle into a disposable runtime directory (never point this at a
# real repository's working tree):
python3 evolution_loop.py --repo-root /path/to/repo --mode full \
  --runtime-dir "$(mktemp -d)"

# Tests
python3 -m unittest test_evolution_loop -v
```

## Relationship to the two existing loops in this repository

| | `horizon/orchestrator.py` | `horizon/controlled_loop.py` | this module |
| --- | --- | --- | --- |
| Domain | workbook report versions | client workbook QA | code/test improvements |
| Stages | Ingest→Validate→Repair→Evaluate→Iterate | Inspect→Plan→Execute→Verify→Score→Repair→Promote→Learn | Observe→Propose→Prioritize→Authorize→Build→Test→Adversarial→Receipt→Learn |
| Bound by | `max_loops` | manifest-declared `acceptance_tests` | one cycle per process invocation |
| Writes | new `_vNNN` versions, never overwrites | staged candidate + promotion package, never the authoritative destination | a disposable sandbox that is deleted before the receipt is written |
| Client evidence | none (report structure only) | verified hashes, never edits originals | none — synthetic fixtures only |

This module intentionally mirrors that family's shape (finite, append-only,
stop-on-no-progress) rather than inventing new vocabulary, so that if/when
issue #68's canonical kernel is built, porting this logic is a rename, not a
redesign.
