# DataBossX Command Brain Alpha — Architecture

- Status: implemented, awaiting independent review
- Scope: `src/databossx/command_brain/`, `migrations/002_command_brain.sql`, `tests/test_command_brain_*.py`
- Data: synthetic fixtures only. No client evidence is registered, read, or produced.

## What this is

A voice-first command layer over DataBossX. It converts a natural-language
request into an inspectable plan and a hashable TaskEnvelope, dispatches bounded
agents against registered artifacts, judges their output against a frozen
baseline, and records an immutable receipt.

It is not a chat bubble in front of a model. The component that decides *what was
asked* is deterministic and rule-based; models are used for work, never for
deciding whether the request was "explain the hold" or "remove it".

## The one rule everything else serves

> **An utterance is an instruction source, not proof of authority.**

Speech and chat can request information, request analysis, and draft work.
Consequential execution requires an authenticated approval bound to an exact
envelope hash. This is enforced in `policy.py` by `AUTHORIZING_SOURCES`, which
deliberately excludes `SPOKEN_UTTERANCE`, `TYPED_UTTERANCE`, `QUOTED_DOCUMENT`,
and `MODEL_OUTPUT`.

## Operating loop

```
LISTEN                voice.VoiceSession / CommandBrain.handle
UNDERSTAND            intent.IntentEngine        (deterministic, rule-based)
RETRIEVE STATE        state.StateRetriever       (sourced + timestamped facts)
IDENTIFY INTENT       intent.NormalizedIntent
IDENTIFY RISK         policy.RiskLevel
BUILD PLAN            planner.Planner            (enumerated steps, no "figure it out")
SELECT AGENTS         roles.ROLES
REQUEST APPROVAL      envelope.EnvelopeDrafter → approvals.ApprovalService
EXECUTE               tools.ToolRegistry → dispatcher.AgentDispatcher
VERIFY                schemas.validate on every agent output
COMPARE               scoring.score_candidate / scoring.compare
ACCEPT/REJECT/QUAR.   judge.judge_candidate      (independent of the producer)
RECORD RECEIPT        store.write_receipt        (hash-chained, append-only)
EXPLAIN               runtime.explain
```

`CommandBrain.handle()` runs the loop up to and including "request approval". It
**cannot execute a consequential plan.** Execution is `approve()` then
`execute()`, two separate calls, and both gates must be open.

## Two independent execution gates

Execution requires *both*:

1. **Mode.** The operator's standing autonomy ceiling permits the envelope's
   level. Approval never raises the mode — that is why "draft only" still blocks
   an already-approved read-only job.
2. **Approval.** An authenticated, unexpired, unconsumed approval whose
   `scope_hash` equals the envelope hash the operator actually read.

Editing any envelope field changes `envelope_hash`, which invalidates the
approval bound to the old one.

## Modules

| Module | Responsibility |
| --- | --- |
| `errors.py` | Typed refusals. Nothing fails open. |
| `util.py` | Canonical JSON/hashing, injectable `Clock`, deterministic IDs. |
| `schemas.py` | Stdlib schema validator + every structured contract. |
| `autonomy.py` | Levels 0–4; `ALPHA_MAX_LEVEL = BOUNDED_WRITER`. |
| `policy.py` | `PolicyProfile`, `ActionRequest`, `PolicyEngine`. Fails closed. |
| `redaction.py` | Secret and absolute-path removal for anything leaving the box. |
| `store.py` | SQLite access + hash-chained append-only ledger and receipts. |
| `tools.py` / `toolset.py` | Allowlisted tool registry and the 24 registered tools. |
| `roles.py` | 13 bounded agent roles with full permission envelopes. |
| `model_gateway.py` | Provider-neutral adapters and honest verification states. |
| `leases.py` | Single-writer leases and monotonic fencing tokens. |
| `envelope.py` | TaskEnvelope, its hash, and its plain-language rendering. |
| `approvals.py` | Scope-bound, expiring, single-use approvals. |
| `intent.py` | Deterministic intent engine + quoted-content separation. |
| `planner.py` | Intent → enumerated plan with per-step autonomy. |
| `state.py` | Operational state, sourced and timestamped. |
| `memory.py` | Typed, sourced memory. Refuses raw chain-of-thought. |
| `synthetic.py` | SYNTHETIC index pages and Runsheet with ground truth. |
| `readers.py` | Four labelled simulated reader profiles. |
| `reconcile.py` | Deterministic index↔Runsheet reconciliation. |
| `scoring.py` | 12 transparent dimensions, 2 of them blocking. |
| `consensus.py` | Cross-candidate agreement; source beats majority. |
| `judge.py` | Independent, deterministic accept/reject/quarantine. |
| `tournament.py` | Tournament engine + bounded improvement loop. |
| `dispatcher.py` | Role/model/authority-gated agent dispatch. |
| `runtime.py` | Assembly: store, gateway, tools, dispatcher, engines. |
| `service.py` | `CommandBrain` — the loop and the command-centre payload. |
| `voice.py` | Voice sessions, activation boundary, correction, stop. |
| `server.py` | Loopback-only stdlib Command Center. |
| `api.py` | Optional FastAPI mount. |
| `demo.py` | Phase 5 controlled demo with self-asserting checks. |

## Autonomy levels

| Level | Name | Meaning |
| --- | --- | --- |
| 0 | OBSERVE | Read status and explain. No jobs created. |
| 1 | DRAFT | Plans, comparison requests, TaskEnvelope drafts. No execution. |
| 2 | READ_ONLY_EXECUTE | Approved inspections, comparisons, tests, synthetic evaluations. |
| 3 | BOUNDED_WRITER | Approved envelope under a valid lease and current fencing token. |
| 4 | RELEASE_OR_EXTERNAL | **Structurally disabled in Alpha.** |

Level 4 is not a default that could be flipped: `PolicyProfile.__post_init__`
refuses to construct with it, `PolicyEngine.elevated` refuses to grant it, and
`ToolRegistry.register` refuses any tool declaring an external effect.

## Tool registry

24 allowlisted tools. Every one takes stable IDs; the server resolves locators
and permissions. `scan_tool_input` rejects, anywhere in the payload:

- filesystem paths (Windows, POSIX, UNC) and `..` traversal
- shell metacharacters and command shapes
- credential-shaped keys and known token formats

A property may opt into relaxed *shell* checking with `x_free_text` for prose
fields; path, traversal, and credential checks are never relaxed.

The registry is frozen before first use, and `ToolContext` exposes no registry,
policy engine, or grant method — a handler has no surface through which to widen
its own permissions.

`stop_queued_job` and `quarantine_candidate` sit at low autonomy on purpose: both
only ever restrict, and an emergency brake that needs a signature is not a brake.

## Model gateway

Adapters declare provider, model, modalities, context limit, tool-use,
structured-output support, locality, cost and latency category, data-sensitivity
policy, permitted project classes, and last-verified time. Verification states:
`VERIFIED`, `LIMITED`, `NOT_VERIFIED`, `OFFLINE`, `QUARANTINED`.

A green state is never assumed. In this repository:

| Model | State | Why |
| --- | --- | --- |
| `deterministic.reconciler`, `deterministic.judge`, `deterministic.commander`, `deterministic.validator`, `human.review_queue` | VERIFIED | In-process, no network, reproducible. |
| `simulated.reader.{careful,conservative,fabricating,transposing}` | LIMITED | Labelled simulators, not real readings. |
| `local.openai_compatible` | NOT_VERIFIED | No transport configured; capability unproven. |
| `handoff.claude_code`, `handoff.codex` | NOT_VERIFIED | Handoff lanes; DataBossX performs no execution and claims none. |

Routing applies hard policy filters first (egress, modality, structured output,
project class, health), then capability. Deterministic work never routes to a
language model.

## Tournament and scoring

Stages: freeze and hash the baseline → run candidates independently → normalize →
reconcile → score → judge independently → accept only on a clean win → otherwise
preserve the baseline and quarantine or reject → write the receipt.

Twelve scoring dimensions; two are **blocking**:

- `hallucination_avoidance` (min 0.95) — confident values invented for unreadable
  or absent cells
- `source_region_support` (min 0.90) — asserted values that cite the correct
  source region

A candidate failing a blocking gate is quarantined regardless of aggregate. A
candidate with a *better* aggregate but a blocking regression is still refused —
volume does not buy its way past a gate.

**Agreement is not evidence.** If any reader reports a cell unreadable, a majority
of confident readings does not overwrite it: the cell becomes
`contested_unreadable`, adopts no value, and is queued for a human.

### REJECT vs QUARANTINE

They are different outcomes and the receipt says which:

- **REJECT** — the candidate simply did not win. Discarded; baseline kept.
- **QUARANTINE** — the candidate failed a blocking integrity gate. Retained for
  inspection, recorded in `cb_quarantine`, and permanently ineligible.

## Persistence

`migrations/002_command_brain.sql` adds `cb_*` tables covering conversations,
voice sessions, transcripts, intents, plans, tools, models, roles, assignments,
jobs, tournaments, candidates, scores, judge decisions, drafts, envelopes,
approvals, leases, artifacts, defects, holds, quarantine, human review, memory,
receipts, and audit events.

It adds no foreign keys into the Phase-2 tables, so it initialises standalone and
rolls back as a pure `DROP` of `cb_*` objects.

`cb_audit_events` and `cb_receipts` are append-only, enforced by SQLite triggers
*and* a hash chain: each entry commits to its predecessor, so
`verify_ledger()` detects a rewrite even if the triggers were removed.

## Command Center

`src/databossx/command_brain/ui/command_center.html` — one self-contained page,
no external requests, desktop and phone layouts, dark and light. Shows the
microphone, transcript, interpreted request, autonomy chip, hold indicator, plan,
agents, live state, disagreements, evidence drawer, and large priority actions.

There is no "Fix everything" button.

Served by `server.py` (stdlib, loopback-only, CSRF + exact-origin + rate limit) or
mounted via `api.py` if FastAPI is present.

## Deliberate non-choices

- **No dependency on one provider.** Everything external is an adapter.
- **No framework lock-in.** Hermes, OpenClaw, and OpenHands may become adapters;
  DataBossX stays the controlling authority and the ledger.
- **No third-party runtime dependency.** The whole subsystem is stdlib, matching
  the repository's existing posture and running on a machine with no PyPI access.
- **No LLM in the intent path.** The decision about what the operator asked for is
  the highest-leverage attack surface in a voice system.
