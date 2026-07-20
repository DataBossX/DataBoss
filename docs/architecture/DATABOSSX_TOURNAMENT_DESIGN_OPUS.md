# DataBossX — Architecture Tournament Response

- AI NAME: Claude Code
- MODEL OR VERSION: claude-opus-4-8 (exact marketing name withheld in this environment; reporting the configured model identifier honestly)
- COMPANY: Anthropic
- DATE: 2026-07-20

> This document is a design proposal for the DataBossX tournament. It is written
> to be combined with other AI systems' answers and handed to Codex and Cursor.
> It aligns with the existing repository blueprint
> (`docs/DATABOSSX_OS_BLUEPRINT.md`): local-first, evidence-grounded,
> human-supervised, no fabrication. Where I disagree with the stated vision, I
> say so directly.

**Legend used throughout:** `[BUILD NOW]` `[BUILD LATER]` `[DO NOT BUILD]`
`[ASSUMPTION]` `[UNCERTAIN]`. "Human judgment required" is called out
explicitly where it applies.

---

## Part 1 — Executive Design

### What DataBossX should actually be

A **single-operator work operating system** built around one durable spine: a
**task graph** whose nodes call **least-privilege workers**, and an **append-only
evidence ledger** that records where every fact came from. Everything else —
agents, tournaments, dashboards, connectors — is a client of that spine. The
product is not "AI"; it is *coordination + provenance*. AI is one class of
worker among deterministic workers (OCR, math, validators, exporters).

The honest one-line test of success: **complete one real land-title project end
to end with zero fabricated conclusions, zero lost evidence, and a reviewer able
to trace every number back to a page image.** If the system cannot do that for
one project, no amount of multi-agent orchestration matters.

### What it should not be

- `[DO NOT BUILD]` An autonomous title examiner or attorney. In Oklahoma,
  marketability opinions are legal work (repo already cites the Abstractors Act
  and Title Examination Standards). The software prepares *draft work product*;
  a licensed human certifies.
- `[DO NOT BUILD]` A model switchboard where "3 AIs agreed" substitutes for a
  document. Consensus is not evidence.
- `[DO NOT BUILD]` A cloud crawler with standing access to every account.
- `[DO NOT BUILD]` An agent framework with unrestricted shell/network/file/email
  access. This is explicitly disallowed and is the fastest path to catastrophe.
- `[DO NOT BUILD, early]` A self-rewriting production system. Self-improvement
  produces *proposals* gated by tests and humans, never silent edits.

### Core design philosophy

1. **Provenance before intelligence.** No fact enters structured storage without
   a link to its source span. A "conclusion" with no evidence chain is a bug.
2. **Determinism where possible, models where necessary.** Interest math,
   fraction reconciliation, and validation are pure functions with property
   tests — never delegated to an LLM. LLMs *propose candidates*; deterministic
   code and humans *confirm facts*.
3. **Least privilege by default.** A worker gets exactly the inputs, tools, and
   network scopes its job needs, granted per-task, revoked on completion.
4. **Everything is auditable and reversible.** Append-only ledger; no
   destructive edits to originals; every automated action carries an actor,
   reason, and undo path.
5. **Human approval on anything irreversible or externally visible.** Sending
   email, spending money, deleting data, releasing a report, changing
   permissions — all gated.
6. **Replaceable modules behind stable interfaces.** OCR, model provider, vector
   store, and queue are all interfaces, not vendors.

### Smallest useful version (the "V0 that earns its keep")

A local web app + local API + Postgres where the operator can:

- Create a Project and drop in documents.
- Documents get hashed, virus-scanned, OCR'd, and indexed; every page is
  addressable and viewable.
- Ask questions and get answers **with citations to page spans** (RAG over that
  project only).
- See a task queue, an evidence view, and an audit log.
- One model provider via a gateway; cost tracked per call.

That is buildable in Phase 0–1 and is genuinely useful on day one. No agents, no
tournaments, no landman calculators yet.

### Ultimate mature version

The full task graph + agent hierarchy + tournament verification + landman title
engine + business connectors + safe self-improvement, all under the same
evidence and permission spine, deployable local-first with optional cloud burst.

### Most important architectural decisions

1. **The evidence ledger is the source of truth**, not any model, chat log, or
   spreadsheet. (Part 3.)
2. **Postgres as the transactional backbone** (relational facts + `pgvector` +
   JSONB + row-level provenance), with a graph *layer* — not a separate graph DB
   — until scale forces otherwise. (Part 14.)
3. **A durable workflow engine (Temporal) as the task graph**, giving
   idempotency, retries, checkpoints, and human-in-the-loop signals for free.
4. **A model gateway that is provider-neutral and policy-aware**, with
   per-request data-classification enforcement (what may leave the machine).
5. **Capability-scoped tool execution in sandboxes**, never raw shell to agents.

### Biggest likely causes of failure (ranked)

1. **Scope explosion.** 20 subsystems at once → nothing finished. Mitigation:
   the phased roadmap forces one working vertical slice first.
2. **Fabricated ownership conclusions** presented as fact. Mitigation: the "no
   evidence, no fact" invariant + deterministic math + reviewer gates (Part 7).
3. **Prompt injection via ingested documents** driving agents to exfiltrate or
   destroy. Mitigation: treat all document text as untrusted data, never
   instructions; capability sandboxing (Part 10).
4. **Silent failure** — a workflow half-completes and no one notices.
   Mitigation: durable workflows + monitoring + an explicit error queue.
5. **Operator overwhelm.** A non-expert can't run a distributed system.
   Mitigation: installers, launchers, safe defaults, one command center.
6. **Data loss / destructive automation.** Mitigation: append-only, backups
   from day one, no automated deletes of originals.

---

## Part 2 — System Architecture

### Layered view

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ OPERATOR SURFACES                                                         │
│  Command Center (web, React/Next)  ·  Chat  ·  Dashboards  ·  Approval    │
│  Queue  ·  Mobile (read/approve)  ·  Voice (later, dictation only)        │
└───────────────┬─────────────────────────────────────────────────────────┘
                │ HTTPS / WebSocket (signed session, MFA)
┌───────────────▼─────────────────────────────────────────────────────────┐
│ API LAYER  (FastAPI)                                                      │
│  REST + WebSocket  ·  AuthN/AuthZ  ·  rate limits  ·  request audit       │
│  OpenAPI schema is the contract; all surfaces & plugins call only this    │
└───────┬───────────────────────────────────┬──────────────────────────────┘
        │                                   │
┌───────▼──────────┐            ┌───────────▼───────────────┐
│ WORKFLOW ENGINE  │  signals   │ MODEL GATEWAY             │
│ (Temporal)       │◄──────────►│  provider-neutral router  │
│  durable task    │            │  policy + data-class gate │
│  graph, retries, │            │  cost/latency accounting  │
│  checkpoints,    │            │  local (Ollama/vLLM) +    │
│  human signals   │            │  cloud (Claude/…)         │
└───┬──────────┬───┘            └───────────┬───────────────┘
    │ activities                            │
┌───▼──────────▼──────────────────────────────────────────────────────────┐
│ WORKER / TOOL RUNTIME  (sandboxed, capability-scoped)                     │
│  OCR · extract · validate(math) · dedupe · export · connectors · code    │
│  Each worker: explicit inputs, tools, net scopes; runs in gVisor/Firecrkr │
└───┬───────────────┬───────────────┬───────────────┬──────────────────────┘
    │               │               │               │
┌───▼─────┐  ┌──────▼──────┐  ┌─────▼──────┐  ┌──────▼───────┐
│ EVENT   │  │ POSTGRES     │  │ OBJECT     │  │ SECRETS      │
│ BUS     │  │  facts +     │  │ STORE      │  │ (Vault/      │
│ (NATS / │  │  pgvector +  │  │ (MinIO/S3, │  │  age+OS      │
│ Redis   │  │  JSONB +     │  │ WORM для   │  │  keychain)   │
│ Streams)│  │  graph edges │  │ originals) │  │              │
└─────────┘  └──────────────┘  └────────────┘  └──────────────┘
        │
┌───────▼──────────────────────────────────────────────────────────────────┐
│ CROSS-CUTTING                                                             │
│  Audit log (append-only, hash-chained)  ·  Observability (OTel→           │
│  Prometheus/Grafana/Loki)  ·  Backups (pgBackRest + restic)  ·  Recovery  │
└───────────────────────────────────────────────────────────────────────────┘
```

### Component responsibilities

- **Frontend** `[BUILD NOW]` — Next.js/React + TypeScript, server components for
  the shell, a thin state layer. Talks only to the API. No business logic.
- **Backend/API** `[BUILD NOW]` — FastAPI (Python). Owns authN/Z, request audit,
  and translation of operator intent into workflow starts + queries. Stateless;
  horizontally scalable.
- **Database** `[BUILD NOW]` — PostgreSQL 16+. Single source of structured
  truth. Schemas in Part 15. Row-level provenance columns are mandatory.
- **Knowledge graph** `[BUILD NOW as tables]` — entities and typed edges stored
  as Postgres tables (`entity`, `edge`) with recursive CTEs for traversal. A
  dedicated graph DB is `[BUILD LATER, UNCERTAIN]` only if traversal depth/scale
  demands it.
- **Vector search** `[BUILD NOW]` — `pgvector` (HNSW index) colocated with facts
  so a chunk's embedding, text, and provenance live in one row. Avoids a second
  datastore and keeps citations trivially joinable.
- **Object/file storage** `[BUILD NOW]` — MinIO locally / S3 in cloud. Originals
  written **once, immutable (object-lock/WORM)**, addressed by SHA-256 content
  hash. Derived artifacts (OCR text, thumbnails) versioned separately.
- **Agent runtime** `[BUILD LATER, Phase 2]` — agents are *workflow definitions*
  that call workers; they do not get their own privileged process. (Part 4.)
- **Workflow engine** `[BUILD NOW, Phase 1–2]` — Temporal. Durable execution =
  free retries, checkpoints, idempotency, timers, and human-approval signals.
- **Message queue** `[BUILD NOW]` — Temporal handles task orchestration; a
  lightweight queue (Redis Streams / NATS JetStream) handles fan-out ingestion
  and event delivery.
- **Event bus** `[BUILD NOW]` — NATS or Redis Streams for `document.ingested`,
  `fact.proposed`, `approval.requested` etc. Enables loose coupling + audit taps.
- **Model gateway** `[BUILD NOW]` — one service all model calls route through.
  Enforces data classification (Part 10), records token/cost, supports fallback
  models and local/cloud routing. Providers behind an interface.
- **Tool execution** `[BUILD NOW, sandboxed]` — tools declared with a manifest
  (inputs, outputs, capabilities). Runs in gVisor/Firecracker or at least a
  locked-down container with no ambient network, egress allowlist only.
- **Authentication** `[BUILD NOW]` — local: OS keychain + passphrase + TOTP MFA.
  Cloud: OIDC. Single operator now, but model it as accounts+roles from day one.
- **Authorization** `[BUILD NOW]` — capability + role model; every API and tool
  call checks a policy (OPA/Casbin). Default deny.
- **Secrets management** `[BUILD NOW]` — HashiCorp Vault (or, minimal, `age`
  encryption + OS keychain). Secrets never in env files committed anywhere.
- **Audit logs** `[BUILD NOW]` — append-only, hash-chained table + object copy.
  Records actor, action, target, reason, before/after hash.
- **Observability** `[BUILD NOW]` — OpenTelemetry traces from API→workflow→worker
  →model; Prometheus metrics; Loki logs; Grafana dashboards. Every model call is
  a span.
- **Backups** `[BUILD NOW — mandatory before real data]` — pgBackRest for
  Postgres (WAL + full), restic for object store to a *separate* encrypted
  target. Tested restores.
- **Recovery** `[BUILD NOW]` — documented, scripted restore; workflow replay from
  Temporal history; RPO/RTO targets (Part 11).
- **Deployment** `[BUILD NOW]` — Docker Compose for local single-box;
  Kubernetes/Nomad `[BUILD LATER]` only if multi-node needed. One `docker
  compose up` + installer for the operator.
- **Local execution** `[BUILD NOW]` — the whole stack runs on one Windows/Linux
  box; local models via Ollama/vLLM.
- **Cloud execution** `[BUILD NOW as option]` — same images, cloud burst for
  heavy OCR/model jobs, gated by data classification.
- **API layer** `[BUILD NOW]` — OpenAPI-first; versioned (`/v1`); the *only* way
  in. Plugins and surfaces are clients.
- **Plugin system** `[BUILD LATER, Phase 5]` — signed manifests, capability
  grants, sandboxed; a plugin is just a registered tool/connector. Never
  in-process untrusted code.

### How the pieces communicate

- Surfaces → **API** (HTTPS/WS).
- API → **Workflow engine** (start workflow / send signal) and → **Postgres**
  (reads).
- Workflow activities → **Workers** → (**Model gateway**, **Postgres**, **Object
  store**, **Connectors**).
- Everything emits to the **Event bus**; the **Audit log** and **Observability**
  subscribe.
- Secrets fetched at call time from **Vault**; never passed through the model
  gateway to a provider.

---

## Part 3 — Source of Truth

**Authoritative truth lives in three tiers, and only one of them is
"believed":**

1. **Immutable source layer (ground truth of *what exists*).** Original files in
   WORM object storage, addressed by SHA-256. This never changes. If a document
   is wrong, you add a new document; you never edit the original.
2. **Derived-evidence layer (ground truth of *what a source says*).** OCR text,
   page geometry, extracted spans — each linked to a source hash + page +
   bounding box. Versioned; reprocessing creates a new version, old kept.
3. **Fact layer (ground truth of *what we assert*).** Structured `Fact` rows.
   **Every fact must reference ≥1 `Evidence` row**, which references a
   source+span. A fact with no evidence is invalid by schema constraint.

| Data type | Where it lives | Mutable? | Rule |
|---|---|---|---|
| Raw files | Object store (WORM) | No | Content-hash addressed; write-once |
| Extracted text | Object store + `document_version` | Versioned | New version on reprocess |
| Structured facts | `fact` table | Append + supersede | Must cite evidence |
| AI-generated conclusions | `fact` with `status='proposed'`, `origin='model'` | Yes (until confirmed) | Never auto-promoted to authoritative |
| Human-approved facts | `fact` with `status='confirmed'`, `approved_by` | Corrected via new version | The only "believed" tier for decisions |
| Conflicting evidence | Multiple `fact` rows in a `claim_group` | — | Never silently merged; flagged |
| Confidence scores | `fact.confidence` (0–1) + method | — | Model confidence ≠ truth; only a triage signal |
| Versions | `*_version` tables, monotonic | — | Never overwrite; supersede pointer |
| Provenance | FK chain fact→evidence→span→doc_version→source | — | Enforced by NOT NULL FKs |
| Citations | Rendered from evidence at read time | — | Generated, never hand-typed |
| Corrections | New version + `superseded_by`; audit event | — | Old value stays visible |
| Deleted/superseded | `status='superseded'` / `retracted`, soft only | — | No hard delete of evidence |

### Confidence model

`confidence ∈ [0,1]` with a required `method` enum (`ocr_char_conf`,
`model_selfreport`, `deterministic`, `human`). **Deterministic and human are the
only methods allowed to back a released conclusion.** Model self-reported
confidence is used *only* to rank the review queue, never to auto-approve.

### Preventing duplicates and contradictions

- **Duplicates:** content-hash dedupe on ingestion for files; for entities
  (Person/Org/Property), an **entity-resolution** step produces a canonical
  entity with `alias` rows and a `merge_confidence`; merges above a threshold are
  auto-linked *but reversible*, below threshold go to a **human review queue**.
- **Contradictions:** facts about the same subject+predicate land in a
  `claim_group`. If values disagree, the group is marked `contested`; the system
  refuses to emit a single "answer" and instead surfaces both with evidence.
  Resolution requires a human decision recorded as a `confirmed` fact that
  `supersedes` the alternatives. **The system never picks a winner by vote.**

---

## Part 4 — Agent System

**Framing:** An "agent" is a *typed workflow* with a persona prompt, a fixed
toolset, a permission scope, and memory-access rules. Agents are not free-running
daemons; they are started, stepped, and stopped by the workflow engine, and
every tool call passes the same authorization + audit as a human's.

### Hierarchy

```text
                       ┌──────────────┐
                       │  COMMANDER   │  (single entry, policy-aware)
                       └──────┬───────┘
                              │ decomposes intent → plan
                       ┌──────▼───────┐
                       │   PLANNER    │  (creates task graph, no side effects)
                       └──────┬───────┘
        ┌──────────┬─────────┼─────────┬──────────┬──────────┐
     Research   Coding    Document    Land    Verification  Ops
     agents     agents    agents    agents      agents     agents
        └──────────┴─────────┴─────────┴──────────┴──────────┘
                  monitored by → Monitoring & Recovery agents
                  gated by      → Security agent (policy checks)
```

### Per-agent specification

| Agent | Purpose | Inputs | Outputs | Permissions | Tools | Memory access | Failure conditions | Human approval |
|---|---|---|---|---|---|---|---|---|
| **Commander** | Turn operator intent into a plan; hold context; route | Operator message, project ctx | Plan proposal, clarifying Qs | Read project; start workflows; no external side effects | planner, query, chat | Read short-term + project | Ambiguous intent, policy conflict | Approves any plan that spends money / sends externally |
| **Planner** | Decompose into a typed task graph | Goal, capabilities registry | Task DAG (no execution) | Read-only | task-graph builder | Read project | Cyclic/unbounded plan → reject | Plan approval for high-risk graphs |
| **Research** | Answer questions from *authorized* corpus + (allowlisted) web | Query, project scope | Cited answer, candidate facts (`proposed`) | Read project docs; web via allowlist proxy | RAG search, web-fetch(allowlist), summarize | Read project + institutional | No citation found → must say "unknown" | None to read; approval to persist facts |
| **Coding** | Implement specs via Codex/Cursor workflow (Part 6) | Spec, repo, tests | Branch + PR, tests | Write only to assigned module dir; no prod deploy | git(branch), test-runner, sandbox build | Read project code memory | Tests fail, touches other module → block | PR merge always human |
| **Document** | Ingest→OCR→classify→extract candidates | File, doc type | doc_version, evidence spans, proposed facts | Read object store; write derived layer | OCR, layout, classifier, extractor | Read doc memory | OCR conf < threshold → queue | Approval to confirm extracted facts |
| **Land** | Build chain of title, compute interests | Confirmed instruments/facts | Runsheet, ownership report (draft) | Read facts; call deterministic math only | title-math (pure fn), chain-builder, gap-detector | Read project + institutional | Gap/conflict/unbalanced fractions → stop & flag | **Mandatory** examiner + attorney review before release |
| **Verification** | Independently check a claim against evidence & tests | Claim/PR/fact | Verdict + reasons | Read-only + test sandbox | test-runner, re-extract, cross-check | Read relevant | Cannot verify → "unverified", never pass | — |
| **Security** | Enforce policy on every risky action | Proposed action | Allow/deny + reason | Policy engine only | OPA/Casbin eval, secret-scan | Read policy | Denies on violation | Escalates denials to operator |
| **Operations** | Run business connectors (email/cal/CRM/accounting) | Task, connector creds (scoped) | Draft messages, records | Per-connector least scope | connector tools (read default) | Read project | External write attempted w/o approval → block | **Every external send/write** |
| **Monitoring** | Watch health, cost, drift, SLAs | Metrics, events | Alerts, error-queue items | Read telemetry | metrics query, alerting | None (system) | Silent failure detection | Notifies; no changes |
| **Recovery** | Restore/replay/rollback on failure | Failure event, checkpoints | Restored state, incident record | Restricted runbook actions only | restore scripts, workflow replay | None | Cannot recover → page operator | Approval for destructive recovery |

### Lifecycle controls (how agents are prevented from "running wild")

- **Creation:** only from the capability registry; an agent type must be
  declared with its permission scope reviewed by a human once.
- **Scheduling:** via Temporal; concurrency caps per agent type; global spend +
  token budget enforced by the model gateway.
- **Stopping:** every agent run has a hard **step budget**, **wall-clock
  timeout**, and **spend cap**; exceeding any → auto-halt + error queue.
- **Retries:** idempotent activities only; exponential backoff; max attempts;
  after that, human.
- **Loop prevention:** planner rejects cyclic graphs; runtime detects repeated
  identical tool calls (same args hash N times) → circuit-break.
- **Evaluation:** each agent type has a golden-task eval set; regressions block
  prompt/model changes (Part 12).
- **Kill switch:** a global `PAUSE_ALL_AGENTS` flag the operator can hit from the
  command center and mobile; workflows honor it at every activity boundary.

---

## Part 5 — Multi-AI Tournament System

**Core stance:** tournaments are a *verification and quality* tool, not a truth
oracle. They reduce variance and catch some errors; they **cannot** establish a
fact that has no evidence. The most important design goal is stated in the
prompt: *avoid several AIs confidently repeating the same wrong answer.* The only
robust defense is **grounding every judgment in checkable artifacts** (evidence
spans, executed tests), not in other models' opinions.

### When to use tournaments

- High-stakes, ambiguous, or subjective tasks: architecture proposals, draft
  legal-adjacent summaries (still human-certified), complex extraction on messy
  documents, code where correctness is testable.
- When cost of a wrong answer ≫ cost of extra model calls.

### When NOT to use tournaments `[DO NOT tournament]`

- Deterministic tasks (math, fraction reconciliation, schema validation) — run
  the deterministic function; a tournament here is waste and adds false
  confidence.
- Retrieval where the answer is a citation — you need the *source*, not a vote.
- Trivial/high-volume/low-stakes tasks — cost blows up.
- Anything where the models share the same failure mode (see below).

### Mechanics

- **Independent generation:** each model gets the *same* prompt with **no
  visibility of others' answers**, different random seeds/temperature where
  applicable, and ideally **provider diversity** (don't run 3 variants of one
  family and call it independent — correlated errors survive).
- **Anonymous judging:** answers stripped of provider identity, order shuffled,
  labeled A/B/C. Judge is a separate model *and* automated checks. Judge never
  told which model produced which answer (bias control).
- **Fact verification (the real work):** every factual claim in a candidate
  answer is checked against **retrieved evidence** or **executed code/tests**,
  not against other answers. Claims without support are struck.
- **Code testing:** candidate code runs in a sandbox against a generated +
  human-curated test suite; pass rate is an objective score, not a judged one.
- **Cost/latency control:** per-tournament budget cap; tiered — cheap/local
  models first, escalate to expensive models only if disagreement or low
  confidence; hard latency deadline with a "best-so-far" fallback.
- **Tie-breaking:** (1) objective checks (tests passed, citations valid); (2)
  more specific + fully-cited answer wins; (3) if still tied, present both to the
  operator. Never coin-flip a fact.
- **Consensus vs minority:** record all answers. A **minority answer that is
  better-evidenced beats a majority that isn't.** Store minority opinions; they
  are early signals of model blind spots.

### Scoring rubric (0–100)

| Dimension | Weight | How scored (objective where possible) |
|---|---|---|
| Groundedness / citation validity | 30 | % of claims backed by verifiable evidence spans |
| Correctness (tests/facts) | 25 | Sandbox test pass rate / deterministic cross-check |
| Completeness | 15 | Coverage of required sub-questions (checklist) |
| Faithfulness (no hallucination) | 15 | # unsupported claims (negative), auto-flagged |
| Safety/policy compliance | 10 | Automated policy scan (no unsafe actions/leaks) |
| Clarity/actionability | 5 | Judge model (lowest weight, most subjective) |

Groundedness + Correctness + Faithfulness = **70%** and are as objective as we
can make them. Judgment (the model's opinion) caps at 5%.

### Avoiding correlated confident errors (the key problem)

1. **Ground, don't vote.** A claim survives only if a *non-model* check supports
   it (retrieved span, executed test, deterministic calc). Agreement among
   models grants **zero** points.
2. **Provider + prompt diversity.** Different families, and at least one
   "adversarial/skeptic" prompt whose job is to *refute* the leading answer.
3. **Mandatory abstention.** Every model must be able to answer "insufficient
   evidence." Confident answers with no citations are penalized, not rewarded.
4. **Red-team judge.** A dedicated verifier prompt tries to find a
   counterexample; if it finds one with evidence, the answer is downgraded
   regardless of consensus.
5. **Human tiebreak on contested high-stakes items.**

### Prompt-leakage prevention

- System/policy prompts are never included in judged content.
- Candidate answers are sanitized (strip any echoed system text, injected
  instructions) before judging.
- Judges see only the task + candidate answers, never the orchestration prompt.

### Storing results for learning `[BUILD LATER for the learning loop]`

Persist `tournament`, `ai_response`, scores, judge rationale, evidence links, and
final human decision. Over time this yields (a) per-model, per-task-type
reliability stats that feed the **model router**, and (b) a labeled dataset of
"models were confidently wrong here" for eval sets.

---

## Part 6 — Codex and Cursor Build Workflow

**Assumption `[ASSUMPTION]`:** "Codex" = an autonomous code-generation agent that
opens PRs from issues; "Cursor" = an interactive IDE agent used for review and
guided edits. Roles below reflect that split.

### Repository structure

Monorepo (Part 16), enforced module boundaries, one CI. Monorepo chosen so a
single spec/PR spans app + service + shared types coherently, and so AI agents
see the whole contract.

### Branch strategy

- `main` protected, always releasable; no direct pushes.
- `develop` `[UNCERTAIN — optional]`; for a single operator, trunk-based off
  `main` with short-lived branches is simpler.
- Feature branches: `feat/<module>/<short>`; agent branches namespaced
  `claude/…`, `codex/…`, `cursor/…` (repo already uses this convention).
- **One module per branch** — enforced by a CODEOWNERS + a CI check that fails a
  PR touching files outside the declared module scope (this is the primary guard
  against "one AI damaging unrelated modules").

### Issue / task format (Codex-ready)

```yaml
id: TASK-014
title: Document ingestion — SHA-256 hashing + WORM write
module: services/ingestion
why: Every file must be content-addressed and immutable before processing.
inputs: [uploaded file, project_id]
outputs: [source row, object-store key, ingest event]
files: [services/ingestion/hash.py, services/ingestion/store.py, tests/…]
dependencies: [TASK-003 object store, TASK-005 db schema]
acceptance:
  - identical bytes → same key, no second write
  - original is object-locked; overwrite attempt fails test
  - emits document.ingested event
tests: [unit: hashing; integration: WORM immutability; property: idempotency]
security:
  - virus scan BEFORE any parsing
  - no path traversal from filename
out_of_scope: [OCR, extraction]  # hard boundary
```

### Specification format

Every non-trivial task carries a short spec: Problem → Interface (types/OpenAPI)
→ Invariants → Acceptance tests → Security notes → Out-of-scope. Interfaces are
defined **before** implementation so agents code to a contract.

### Coding standards

- Python: ruff + black + mypy (strict); TS: eslint + prettier + tsc strict.
- No function does I/O and logic in one place (testability).
- Pure functions for all math/validation.
- Conventional Commits.

### Testing requirements

- Unit + integration + property tests for anything with invariants (interest
  math especially). CI must be green; coverage gate on changed lines.
- Golden-file tests for extraction and reports.

### Security review

- `gitleaks` (repo already has `.gitleaks.toml`) + dependency audit (pip-audit,
  npm audit) + `semgrep` in CI. Any new capability/tool manifest triggers a
  human security review label.

### Code review

- **Two-stage:** (1) automated (CI + Cursor review prompt below), (2) human
  merge. AI may *review*; a human *approves merge*. Non-negotiable for anything
  touching security, money, or the evidence ledger.

### Documentation / migrations / rollbacks / release

- Docs updated in the same PR (enforced for public API changes).
- Migrations: Alembic, forward + tested down-migration; never destructive without
  a backup step; migrations reviewed by human.
- Rollback: every release is a tagged, reproducible image; `git revert` + prior
  image redeploy; DB migrations designed reversible.
- Release: semver tags, changelog, staged (local → operator canary → default).

### Automated verification

CI pipeline: lint → typecheck → unit → integration → property → security scan →
build image → smoke test. Merge blocked unless all pass.

### Who does what

- **Codex writes code** for well-specified, testable, single-module tasks
  (most of Parts 15–18).
- **Cursor is used** for interactive exploration, cross-cutting refactors under
  human eye, debugging, and *review*.
- **Another AI reviews** (tournament-style) for security-sensitive modules and
  the title-math engine.

### Preventing cross-module damage

- CODEOWNERS + module-scope CI check (touch only declared paths).
- Public interfaces are versioned; breaking a shared type fails downstream CI.
- No agent has deploy rights; merge is human.

### Preserving context across sessions

- A living `docs/architecture/` + per-module `README` + `CONTEXT.md` with current
  invariants; agents read these first.
- The evidence/decision ledger includes **architecture decision records (ADRs)**.
- Each task references its spec by ID; PRs link the ADR they honor.

### Reusable master build prompt for Codex

```text
You are implementing ONE task in the DataBossX monorepo. Follow it exactly.

CONTEXT (read first, do not skip):
- docs/architecture/*.md and the module's README.md and CONTEXT.md
- The task spec below (TASK-XXX)

HARD RULES:
1. Modify files ONLY within the module path declared in the spec. Touching any
   other path fails CI and is forbidden.
2. Code to the declared interface/OpenAPI. Do not change public types without an
   ADR.
3. All math/validation must be pure, deterministic, and property-tested. Never
   use an LLM for arithmetic, fractions, or interest calculation.
4. No new network egress, secret access, shell execution, or file deletion
   unless the spec's `security` block explicitly grants it. Default deny.
5. Every fact-producing code path must attach provenance (evidence link). No
   evidence → do not persist as a fact.
6. Write tests FIRST for every acceptance criterion; make them fail, then pass.

DELIVERABLE:
- A branch feat/<module>/<slug>, all tests green locally, docs updated, a PR
  body that lists: what changed, which acceptance criteria are covered by which
  test, security considerations, and anything out of scope you intentionally
  skipped.

If the spec is ambiguous or under-specified, STOP and open a clarifying
question in the PR description instead of guessing.
```

### Reusable review prompt for Cursor

```text
You are REVIEWING a DataBossX PR. You do not merge. Produce findings only.

Check, in order:
1. Scope: does the diff touch only the declared module? Flag any out-of-scope
   file. (Blocker.)
2. Invariants: is provenance attached to every persisted fact? Is all math
   deterministic and property-tested? (Blocker if violated.)
3. Security: new egress, secrets, shell, file deletion, or broad CORS? Injection
   handling for any ingested/document text (treated as data, never
   instructions)? (Blocker.)
4. Tests: does each acceptance criterion map to a passing test? Are failure
   paths tested? Any assertion that would pass on wrong behavior?
5. Correctness: reason about edge cases the tests miss; try to construct a
   failing input.
6. Reversibility: migrations reversible? Destructive ops backed up first?

Output: a table of findings {severity, file:line, issue, suggested fix}. Mark
CONFIRMED vs PLAUSIBLE. If you find a concrete failing input, include it. Do not
approve; recommend APPROVE/REQUEST-CHANGES with reasons.
```

---

## Part 7 — Landman Intelligence

This is DataBossX's differentiator and its highest-risk subsystem. The
governing rule: **the software extracts and computes; a licensed human
concludes.**

### Pipeline

```text
Instrument image
 → OCR (+ geometry)                      [Document agent]
 → instrument classification             (deed/lease/assignment/probate/…)
 → span extraction (grantor, grantee, legal desc, book/page, dates, interest)
 → normalization (names, legal descriptions, dates)
 → entity resolution (link to canonical Person/Org/Property)
 → CANDIDATE facts (status=proposed, with evidence spans)
 → human review queue (confirm/reject/edit each field)
 → CONFIRMED instruments
 → deterministic chain-of-title builder
 → deterministic interest math (WI/NRI/royalty) as exact fractions
 → gap + conflict detection
 → runsheet + ownership report (DRAFT)
 → examiner review → (attorney review where legally required) → release
```

### Data model (see Part 15 for schemas)

- `Property` (surveyed unit) → `Tract` (specific interest parcel) with legal
  description (section-township-range / lot-block / metes-and-bounds, county
  variant flagged).
- `Instrument` (deed, lease, assignment, probate order, affidavit) with
  grantor/grantee edges, recording info (book/page/instrument#/date), and
  evidence links.
- `OwnershipInterest`: `(party, tract, instrument, type[WI|RI|ORRI|NPRI|surface],
  fraction, decimal, effective_date, evidence[])`. **Fractions stored as exact
  rationals** (numerator/denominator), never floats.
- `Lease`: lessor/lessee, royalty fraction, term, extensions, burdens.
- Chain of title = ordered instruments per tract; runsheet = the chronological
  render.

### Calculation model (deterministic, testable)

- Interest math is a **pure library** using exact rational arithmetic
  (`fractions.Fraction`). WI, NRI = WI × (1 − burdens), royalty burdens, ORRI all
  computed by explicit formulas with unit + property tests.
- **Balancing invariants** (hard checks): total WI in a tract = 1 (100%); NRI ≤
  WI; sum of royalty + working NRI reconciles. A tract that does not balance is
  `contested` and **cannot be released** — it goes to review with the imbalance
  shown. (Repo's `horizon/` already has fraction math + validation to reuse.)

### Gap & conflict detection

- **Gap:** a break in the chain (missing conveyance between two owners, undated
  transfer, orphaned interest). Detected structurally, flagged, never
  "assumed filled."
- **Conflict:** two instruments conveying overlapping interest, double
  conveyance, name collisions. Surfaced as `contested` claim groups.

### Name normalization & entity matching

- Deterministic normalization (case, suffixes Jr/Sr, "et ux", "&"/and,
  entity suffixes LLC/LP) + a candidate-match step; matches above threshold
  auto-linked (reversible), below → human queue. Aliases preserved.
- County-specific variations captured in a `county_profile` (recording format,
  legal-description style, common abbreviations) so extraction rules adapt.

### Preventing fabricated ownership conclusions (the crux)

1. **No conclusion without a confirmed chain.** Ownership output is a *function*
   of confirmed instruments; if inputs are unconfirmed/contested, the output is
   labeled DRAFT/INCOMPLETE and the specific gap is named.
2. **LLMs never assert ownership.** They extract candidate spans only. The
   ownership number comes from deterministic math over human-confirmed facts.
3. **Balancing invariants must hold** or release is blocked.
4. **Every number in the report is click-through to its evidence span.** A number
   with no evidence chain cannot render.
5. **Mandatory examiner review; attorney review where the jurisdiction requires
   it** (Oklahoma marketability = legal work). The system prints a standing
   disclaimer: *draft work product, not a title opinion.*
6. **Human judgment required** for: heirship/probate interpretation, ambiguous
   legal descriptions, and any contested chain. The system presents evidence and
   options; it does not decide.

---

## Part 8 — Document Intelligence

### Pipeline stages (each a workflow activity, each idempotent)

```text
1. Ingestion      : accept file, capture source metadata, SHA-256, WORM write
2. Malware scan   : ClamAV + type/really-a-PDF check BEFORE any parser touches it
3. Pre-flight     : detect type (PDF text vs scanned, image, docx, xlsx, eml,
                    html, map, handwriting); page count; corruption check
4. OCR            : text PDFs → embedded text; scanned/image → OCR engine with
                    per-char confidence + bounding boxes; handwriting → higher
                    review flag
5. Layout         : detect columns, tables, headers, signature blocks, stamps
6. Classification : document class (deed/lease/invoice/email/…) → routing
7. Extraction     : class-specific field extraction → candidate spans + facts
8. Validation     : schema + business rules (dates sane, book/page format,
                    fractions parse); OCR conf < threshold → review
9. Deduplication  : content-hash exact; near-dup via embeddings (report, don't
                    auto-delete)
10. Chunking      : layout-aware chunks with page+bbox anchors (not blind
                    fixed-size) for retrieval
11. Indexing      : embeddings → pgvector; text → full-text; facts → tables
12. Citation gen  : every chunk/fact carries doc+page+bbox for click-through
13. Human review  : low-confidence / contested items queued
14. Reprocessing  : re-run any stage → new version, old retained
15. Versioning    : document_version chain; supersede pointers
```

### Per-input handling

| Input | Handling |
|---|---|
| PDF (text) | Extract embedded text + layout; no OCR needed |
| Scanned PDF | OCR with geometry; confidence per token |
| Images | OCR; EXIF stripped; re-encoded to strip active content |
| Word (.docx) | Structured parse (python-docx); track changes noted |
| Excel (.xlsx) | Table extraction; formulas captured; **used as data, not truth** |
| Email (.eml/msg) | Header + body + attachments recursed through same pipeline |
| Web pages | Fetch via allowlist proxy, sanitize, snapshot to WORM (provenance = URL+timestamp+hash) |
| Maps | Store image; `[BUILD LATER]` georeferencing; manual annotation now |
| Handwriting | OCR best-effort, **always** review-queued, never auto-confirmed |
| Tables | Layout-aware table extraction → structured rows with cell provenance |
| Legal forms | Template-aware field extraction per known form type |

**Security note (mandatory):** malware scan and content-type verification happen
**before** any parser runs; parsers run sandboxed; document text is **untrusted
data** and is never interpreted as instructions to any agent (prompt-injection
defense).

---

## Part 9 — Memory and Knowledge Graph

| Layer | Contents | Store | Expiry | Notes |
|---|---|---|---|---|
| Short-term | Current conversation/task context | In-workflow state / Redis | End of task/session | Never silently persisted |
| Project memory | Facts, docs, decisions for one project | Postgres (scoped by project_id) | Project lifetime | Default read scope for agents |
| Personal preferences | Operator settings, formats, defaults | Postgres `preference` | Until changed | Explicit, editable, listed in UI |
| Institutional | Cross-project reusable knowledge (county profiles, templates) | Postgres, curated | Curated | Promotion is a reviewed action |
| Semantic search | Embeddings of chunks/facts | pgvector | With source | Rebuilds on reprocess |
| Structured knowledge | Entities + typed edges | Postgres `entity`/`edge` | Versioned | The "graph" |
| Temporal knowledge | Valid-time on facts (`effective_date`, `recorded_date`, `observed_at`) | Postgres | — | Enables "what did we know when" |
| Relationships | grantor→grantee, owns, party-of | `edge` table | Versioned | Traversal via CTE |

### Correction & expiration

- **Correction:** never in place — new version + `supersedes`; audit event; old
  visible. Memory the model relied on that later proves wrong is retracted and
  downstream facts re-flagged.
- **Expiration:** short-term auto-expires; project/institutional are curated, not
  auto-forgotten (data loss risk). Optional retention policies per project.

### Sensitive-memory controls

- PII/financial fields tagged at ingest; access requires elevated scope; can be
  redacted in model prompts (send hashes/placeholders when a cloud model
  doesn't need the raw value).

### What should NEVER be automatically remembered `[explicit]`

- Secrets, credentials, API keys, passwords.
- Full SSNs, bank/account numbers, card numbers (store masked if ever needed).
- Anything the operator marks "do not retain."
- Raw contents of a document the operator has not authorized for indexing.
- One project's confidential data promoted into cross-project memory **without an
  explicit human promotion step** (prevents client-data leakage across matters).
- Model chit-chat / unverified model assertions as "facts."

---

## Part 10 — Security

**Threat model → control (with mandatory-before-production flags ⭐):**

| Threat | Primary controls |
|---|---|
| **Prompt injection (via docs/web)** ⭐ | Treat all ingested text as untrusted data, never instructions; agents can't execute arbitrary actions from content; tool calls need explicit params from the *plan*, not from document text; output-side allowlist for actions |
| **Malicious documents** ⭐ | Malware scan + type verification before parsing; sandboxed parsers; strip active content |
| **Credential theft** ⭐ | Secrets in Vault/keychain, never in code/env-in-repo; scoped, short-lived tokens; gitleaks in CI |
| **Data exfiltration** ⭐ | Egress allowlist; data-classification gate on model gateway (what may leave the box); per-connector scopes; DLP checks on external sends |
| **Rogue agents** ⭐ | Capability sandboxing; step/spend/time budgets; kill switch; default-deny authz |
| **Excessive permissions** ⭐ | Least privilege; per-task grants; human review of any new capability |
| **Supply-chain attacks** | Pinned deps + lockfiles; hash verification; pip-audit/npm-audit/semgrep; minimal base images |
| **Insecure dependencies** | Automated CVE scanning gates CI; renovate with human approve |
| **Model-provider leaks** ⭐ | Data-classification routing (confidential → local model only); no confidential doc auto-sent to cloud; provider DPA review; redaction |
| **Local malware** | Full-disk encryption; least-privilege OS user for the stack; no agent shell |
| **Compromised plugins** | Signed manifests; sandbox; capability grants; revocation |
| **API abuse** | AuthN + rate limits + audit; input validation; no unauth endpoints |
| **Destructive commands** ⭐ | No raw shell to agents; destructive ops require approval + backup precondition |
| **Accidental deletion** ⭐ | Soft-delete only; WORM originals; backups; undo |
| **Insider misuse** | Full audit trail; approvals; role separation (even single operator: a "review" identity vs "admin") |
| **Backup compromise** ⭐ | Encrypted, offsite/separate-credential backups; restore tests; immutability |

### Definitions (concrete)

- **Least privilege:** default deny; each worker's manifest lists allowed
  inputs, tools, egress hosts; granted per task, revoked on completion.
- **Sandboxing:** workers/tools in gVisor/Firecracker (or hardened container);
  no ambient network; egress via a filtering proxy with an allowlist.
- **Network restrictions:** deny-all egress except allowlist; internal services
  on a private network; only the API is exposed (localhost by default).
- **Approval gates:** money, external send, deletion, permission change, report
  release, new capability — all require explicit operator approval.
- **Secret storage:** Vault or `age`+OS keychain; short-lived tokens; rotation
  (repo already mandates rotation in `SECURITY.md`).
- **Encryption:** TLS in transit (even localhost for cloud parity); AES-256 at
  rest (disk + object store + DB); field-level for PII.
- **AuthN:** passphrase + TOTP MFA locally; OIDC in cloud.
- **AuthZ:** OPA/Casbin policy on every API + tool call.
- **Audit logging:** append-only, hash-chained; actor/action/target/reason/
  before-after; tamper-evident.
- **Data retention:** per-classification policy; legal-hold support; documented
  deletion (soft, with approval).
- **Incident response:** runbook; kill switch; credential rotation; forensic
  audit export; operator notification path.
- **Emergency shutdown:** `PAUSE_ALL_AGENTS` + `HALT_EGRESS` flags reachable from
  command center and mobile; workflows honor at activity boundaries.
- **Recovery:** tested restore from backups; workflow replay; documented RPO/RTO.

**Mandatory before first production use (⭐ above), minimum set:** malware scan +
sandboxed parsing, secrets in a vault (never in repo), egress allowlist +
data-classification gate, no raw shell/network to agents, least-privilege authz
default-deny, append-only audit log, encrypted + tested backups, soft-delete +
WORM originals, MFA on the operator account, kill switch. **Do not process real
client data until all of these exist.**

---

## Part 11 — Reliability and Self-Healing

| Failure | Detection | Response |
|---|---|---|
| Agent crash | Workflow activity failure/heartbeat timeout | Retry (idempotent) → error queue → operator |
| Model outage | Gateway health + error rate | Circuit-break → fallback model (incl. local) → degrade |
| API failure | Timeouts, 5xx metrics | Backoff retry; circuit breaker; cached/degraded response |
| Bad outputs | Validators, verification agent, schema checks | Reject; re-run with different model; queue if persistent |
| Corrupt files | Hash mismatch, parser error | Quarantine; flag; never overwrite; re-fetch source |
| Database failure | Health probe, replica lag | Failover to replica; read-only degraded mode; page operator |
| Network outage | Connectivity probe | Local-only mode (local models, queued external work) |
| Full disk ⭐ | Disk metric threshold | Alert early; block new ingestion; GC derived artifacts (never originals) |
| Expired credentials | Auth error class + pre-expiry monitor | Pause connector; prompt re-auth; don't loop-fail |
| Queue congestion | Backlog depth metric | Backpressure; shed low-priority; scale workers |
| Infinite loops | Repeated identical tool-call hash / step budget | Circuit-break; halt agent; error queue |
| Duplicate jobs | Idempotency keys | Dedupe; second run is a no-op |
| Partial workflows | Temporal history shows incomplete | Resume from checkpoint or compensate (saga) |
| Broken updates | Smoke test fails post-deploy | Auto-rollback to last good image |

**Principles:** idempotent activities keyed by content hash; checkpoints via
Temporal history; sagas/compensation for multi-step external effects; circuit
breakers per dependency; explicit fallback-model chain; **degraded operation is a
first-class mode** (e.g., "local-only, cloud unavailable" clearly shown to the
operator, not a silent stall). **Every failure creates a visible error-queue
item — silence is the enemy.**

---

## Part 12 — Self-Improvement

**Non-negotiable:** the system may *propose*; it may never *silently rewrite
production.* Every change flows through the same Codex/Cursor PR + CI + human
merge pipeline as any other code.

| Change class | Autonomy allowed |
|---|---|
| Measure performance, collect metrics | ✅ Autonomous (read-only) |
| Compare prompts on eval sets; recommend | ✅ Autonomous (produces a report) |
| Generate candidate test cases | ✅ Autonomous, but tests reviewed before adopted |
| Improve routing weights (model router) | ⚠️ Autonomous **within bounds** (only reweights among already-approved models; bounded step; logged; reversible) |
| Suggest extraction-rule improvements | ⚠️ Proposal → shadow-eval → human adopt |
| Suggest code changes | ⚠️ Opens a PR; **tests required**; human merge |
| Update documentation | ⚠️ PR; human merge (low risk but still reviewed) |
| Open pull requests | ✅ Allowed to open; ❌ never to merge |

**Requires tests:** any code/extraction/schema change. **Requires review:** any
prompt change affecting production, routing beyond bounds, new tool/capability.
**Requires human approval:** merges, migrations, model-provider changes, anything
touching security/money/evidence-ledger. **Never autonomous `[DO NOT BUILD as
autonomous]`:** editing the audit log, changing permission policy, deleting data,
modifying the interest-math library, releasing reports, altering safety controls.

**Mechanism:** a nightly "improvement" workflow runs evals, produces a ranked
report of proposals with expected impact and risk, and for code-level items opens
draft PRs. The operator reviews a single digest. **Shadow mode** for extraction/
prompt changes: run new vs current in parallel on real inputs, compare against
human-confirmed outcomes, and only surface a proposal when it beats baseline on
the golden set.

---

## Part 13 — User Experience

Design target: a non-expert operator runs the whole system without reading code.

- **Command Center** `[BUILD NOW]` — one screen: what's running, what needs me
  (approvals/errors), recent evidence, cost today, system health, big red PAUSE.
- **Chat** `[BUILD NOW]` — natural-language entry to the Commander; answers cite
  evidence; every action it proposes shows an explicit confirm.
- **Dashboard** `[BUILD NOW]` — projects, throughput, cost, queue depth, health.
- **Project view** `[BUILD NOW]` — documents, facts, chain, tasks for one matter.
- **Document view** `[BUILD NOW]` — page images with highlight overlays; click a
  fact → jumps to its span.
- **Evidence view** `[BUILD NOW]` — for any conclusion, the full provenance
  chain, with contested items shown side-by-side.
- **Agent view** `[BUILD LATER, Phase 2]` — running agents, budgets, step logs,
  stop button.
- **Approval queue** `[BUILD NOW]` — everything gated (sends, spends, releases,
  merges) in one list; approve/deny with reason.
- **Error queue** `[BUILD NOW]` — every failure, triage state, retry/dismiss.
- **Cost view** `[BUILD NOW]` — per model/provider/project/day; budgets + alerts.
- **Security view** `[BUILD LATER, Phase 2]` — audit search, permission grants,
  active egress, recent denials.
- **Automation builder** `[BUILD LATER, Phase 4]` — visual composition of
  existing, vetted workers into a workflow (no arbitrary code).
- **Settings** `[BUILD NOW]` — providers, keys (write-only), data-class policy,
  retention, backups, preferences.
- **Mobile** `[BUILD LATER, Phase 5]` — read + approve + pause only; no admin.
- **Voice** `[BUILD LATER, Phase 5, UNCERTAIN value]` — dictation/queries only;
  **never** voice-authorized irreversible actions.

Cross-cutting UX rules: safe defaults; every irreversible action is a two-step
confirm; the system always shows *why* it believes something (evidence-first);
plain-language error messages with a suggested next step.

---

## Part 14 — Recommended Technology Stack

Bias: proven, boring, replaceable. Each behind an interface to limit lock-in.

| Area | Recommendation | Why it fits | Alternatives | Tradeoffs / lock-in | Security | Ops complexity |
|---|---|---|---|---|---|---|
| Backend language | **Python 3.12** | Best OCR/ML/doc ecosystem; team + repo already Python | Go, TS | Slower CPU; GIL → use workers | Mature tooling | Low |
| Frontend | **TypeScript + Next.js/React** | Rich UI, SSR, one language front | SvelteKit, Remix | React churn | Well-trodden | Low–med |
| Desktop shell | **Tauri** (wrap the web app) | Small, secure, Rust core, local FS with permissions | Electron | Electron = big + broader attack surface | Tauri safer default | Low |
| DB | **PostgreSQL 16** | Relational + JSONB + pgvector + FTS in one; ACID | MySQL, CockroachDB | Single-writer scaling later | RLS, encryption | Low |
| Graph | **Postgres tables + CTEs** now; Neo4j `[LATER]` | Avoids 2nd datastore; edges are just rows | Neo4j, ArangoDB | Deep traversal slower | One store to secure | Low |
| Vector | **pgvector (HNSW)** | Colocated with facts → trivial citation joins | Qdrant, Weaviate | Very large scale → dedicated | One store | Low |
| Workflow | **Temporal** | Durable execution, retries, human-in-loop, replay | Prefect, Airflow, custom | Learning curve; a service to run | Deterministic, auditable | Med |
| Queue/bus | **NATS JetStream** or **Redis Streams** | Simple, fast, durable enough | Kafka, RabbitMQ | Kafka = heavy for one operator | Auth + TLS | Low–med |
| Containers | **Docker + Compose** (Nomad/K8s later) | One-box simplicity; installer-friendly | K8s | K8s overkill for single operator | Image scanning | Low |
| Sandboxing | **gVisor / Firecracker** | Strong isolation for untrusted parsing/tools | plain containers, nsjail | Setup cost | High isolation | Med |
| Local models | **Ollama** (dev) / **vLLM** (throughput) | Confidential-data inference on-box | LM Studio, llama.cpp | Hardware-bound quality | Data stays local | Med |
| Cloud models | **Provider-neutral gateway** (Claude + ≥1 alt) | Diversity for tournaments; no single dependency | direct SDKs | Provider lock-in if not abstracted | Data-class gate | Low |
| OCR | **Tesseract** baseline + **PaddleOCR**; cloud OCR `[optional]` behind interface | Local-first, provider-neutral | Azure/AWS/Google OCR, Textract | Cloud OCR = data leaves box | Route by classification | Med |
| AuthN | **Passphrase + TOTP** local; **OIDC** cloud | Standard, no custom crypto | passkeys `[LATER]` | — | MFA | Low |
| Secrets | **Vault** (or `age`+keychain minimal) | Central, rotatable, audited | SOPS, cloud KMS | Vault = a service | Strong | Med |
| Monitoring | **OpenTelemetry + Prometheus + Grafana + Loki** | Standard, self-hostable | Datadog (SaaS) | SaaS = data egress | Self-host keeps data in | Med |
| Testing | **pytest + hypothesis** (property) + **Playwright** (e2e) | Property tests catch math bugs | unittest | — | — | Low |
| Deployment | **Compose + tagged images + installer** | Operator-friendly | K8s, PaaS | — | Reproducible | Low |

`[DO NOT BUILD]` a custom workflow engine, a custom vector DB, or a bespoke agent
framework — all are solved; building them is where projects die.

---

## Part 15 — Data Models and APIs

Representative schemas (Postgres, abbreviated; all have `id uuid pk`, `created_at`,
`updated_at`, `created_by`). Provenance FKs are `NOT NULL` where noted.

```sql
project(id, name, client_ref, status, retention_policy, created_by)

task(id, project_id fk, workflow_id, type, status, priority, spend_cap_cents,
     step_budget, deadline, input jsonb, result jsonb, error_id fk null)

workflow(id, name, version, definition_ref, status)

agent(id, type, persona_ref, permission_scope jsonb, model_pref, enabled bool)

document(id, project_id fk, source_id fk, current_version_id fk, doc_class,
         status)  -- status: ingested|scanned|extracted|reviewed
source(id, sha256 unique, object_key, mime, byte_size, virus_scanned bool,
       origin jsonb)  -- WORM; immutable
document_version(id, document_id fk, version int, ocr_object_key, layout jsonb,
                 supersedes fk null, created_by)

fact(id, project_id fk, subject_entity_id fk, predicate, value_json,
     value_fraction_num bigint null, value_fraction_den bigint null,
     status, origin, confidence numeric, method,          -- status: proposed|confirmed|contested|superseded|retracted
     claim_group_id fk, superseded_by fk null,
     approved_by null, CONSTRAINT must_cite CHECK (...))   -- enforced via evidence
evidence(id, fact_id fk NOT NULL, document_version_id fk NOT NULL,
         page int, bbox jsonb, text_span text, extractor, extractor_conf numeric)
citation(view: renders evidence → {doc, page, bbox, url})

entity(id, type, canonical_name, attrs jsonb)             -- Person|Org|Property
edge(id, from_entity fk, to_entity fk, type, valid_from, valid_to, evidence_id fk)
alias(id, entity_id fk, name, match_confidence, source_fact_id fk)

person(entity_id fk, full_name, normalized_name, suffix, dob null)
organization(entity_id fk, legal_name, org_type, jurisdiction)
property(entity_id fk, description, county, state)
tract(id, property_id fk, legal_desc jsonb, county_profile_id fk)
instrument(id, tract_id fk, type, grantor_entity fk, grantee_entity fk,
           book, page, instrument_no, recorded_date, effective_date,
           document_id fk, status)
ownership_interest(id, party_entity fk, tract_id fk, instrument_id fk,
                   interest_type,                          -- WI|RI|ORRI|NPRI|surface
                   fraction_num bigint, fraction_den bigint,  -- exact rational
                   decimal numeric, effective_date, evidence_ids uuid[],
                   status)
lease(id, tract_id fk, lessor_entity fk, lessee_entity fk,
      royalty_num bigint, royalty_den bigint, term jsonb, burdens jsonb,
      document_id fk)

ai_response(id, task_id fk, tournament_id fk null, provider, model, prompt_hash,
            response_text, tokens_in, tokens_out, cost_cents, latency_ms,
            claims jsonb, groundedness numeric)
tournament(id, task_id fk, question, rubric jsonb, winner_response_id fk null,
           consensus jsonb, minority jsonb, human_decision jsonb, status)
approval(id, subject_type, subject_id, requested_by, action, risk, reason,
         status, decided_by null, decided_at null)         -- pending|approved|denied
audit_event(id, ts, actor, action, target_type, target_id, reason,
            before_hash, after_hash, prev_event_hash)       -- hash-chained
error(id, task_id fk null, category, severity, message, context jsonb,
      status, resolution null)                              -- open|triaged|resolved
model_usage(id, ai_response_id fk, provider, model, tokens_in, tokens_out,
            cost_cents, latency_ms, project_id fk, ts)
cost_record(id, project_id fk, period, provider, amount_cents, breakdown jsonb)
```

### Example API / service interfaces (`/v1`, OpenAPI-first)

```
POST /v1/projects                         create project
POST /v1/projects/{id}/documents          upload → returns ingest task
GET  /v1/documents/{id}                    metadata + versions
GET  /v1/documents/{id}/pages/{n}          page image + overlays
POST /v1/query                             {project_id, question} → cited answer
GET  /v1/facts/{id}                         fact + full evidence chain
POST /v1/facts/{id}/confirm                human confirm (approval-gated)
GET  /v1/tracts/{id}/chain                  chain of title (deterministic)
GET  /v1/tracts/{id}/ownership             ownership report (draft/final flag)
POST /v1/tasks                             start a workflow task
GET  /v1/tasks/{id}                         status/result
POST /v1/tournaments                       run tournament {task, models, rubric}
GET  /v1/approvals?status=pending          approval queue
POST /v1/approvals/{id}/decide             approve/deny + reason
GET  /v1/errors?status=open                error queue
GET  /v1/costs?group_by=project            cost view
POST /v1/system/pause-agents               emergency stop
GET  /v1/audit?target=…                     audit search
```

Internal service interfaces (behind the API): `ModelGateway.complete(request,
data_class)`, `OCR.process(source) -> version`, `TitleMath.compute(tract) ->
report`, `Sandbox.run(tool_manifest, inputs)`, `Policy.check(actor, action,
target) -> allow/deny`.

---

## Part 16 — Repository Structure

```text
DataBossX_Final_Modular/
├─ apps/
│  ├─ command-center/        # Next.js web UI (client of the API only)
│  └─ desktop/               # Tauri shell wrapping the web app
├─ services/
│  ├─ api/                   # FastAPI: authN/Z, routing, request audit
│  ├─ ingestion/             # hash, WORM write, malware scan
│  ├─ ocr/                   # provider-neutral OCR interface + engines
│  ├─ extraction/            # classification + field extraction
│  ├─ title-engine/          # deterministic chain + interest math (PURE)
│  ├─ model-gateway/         # provider-neutral, policy + cost + fallback
│  ├─ workflow/              # Temporal worker registrations
│  └─ tournament/            # generation, judging, scoring
├─ libs/                     # shared, versioned
│  ├─ schemas/               # pydantic/TS types = the contract (single source)
│  ├─ evidence/              # provenance helpers, citation rendering
│  ├─ title-math/            # exact-fraction library (property-tested)
│  ├─ policy/                # OPA/Casbin bindings, capability model
│  └─ observability/         # OTel setup
├─ agents/                   # agent personas + toolsets (typed workflows)
├─ workflows/                # workflow definitions (task graphs)
├─ prompts/                  # versioned prompts (repo already has prompts/)
├─ connectors/               # email, calendar, files, CRM, accounting (scoped)
├─ security/                 # policies, sandbox profiles, threat model, IR runbook
├─ infra/                    # docker-compose, images, vault config, k8s(later)
├─ migrations/               # Alembic (repo already has migrations/)
├─ config/                   # env schemas, data-class policy (repo has config/)
├─ scripts/                  # installers, launchers, backup/restore (repo has scripts/)
├─ tests/                    # cross-service integration + e2e (repo has tests/)
├─ docs/                     # architecture, ADRs, runbooks (repo has docs/)
├─ data/        (gitignored) # local runtime data
├─ logs/        (gitignored)
└─ backups/     (gitignored)
```

**Module boundaries (enforced):** `libs/schemas` is the only shared type source;
services depend on libs, never on each other's internals — they talk via the API
or events. `title-math` and `evidence` are pure and have zero I/O. A CI check
fails any PR importing across service boundaries or touching files outside its
declared module. `security/`, `migrations/`, and `title-math/` changes require a
human reviewer label.

This **preserves and refactors** the repo's existing assets: `horizon/` →
`libs/title-math` + `services/title-engine`; `doto_image_commander/` →
`services/ocr` + `connectors`; `grocery_report_pipeline.py` → split into
`services/extraction` workers; `mineral_deal_room/` → folds into
`apps/command-center`. (Matches the blueprint's migration table.)

---

## Part 17 — Build Roadmap

**Phase 0 — Foundation** (`[BUILD NOW]`)
- Deliverables: monorepo layout, CI (lint/type/test/security), Docker Compose,
  Postgres + migrations, object store (WORM), secrets vault, audit log skeleton,
  test harness, threat model doc, backup/restore scripts.
- Dependencies: none.
- Acceptance: `docker compose up` runs; CI green; a file written to object store
  is immutable; backup+restore round-trips; audit log hash-chains verify.
- Risks: over-engineering infra. Mitigation: single-box Compose only.
- Security: secrets vault, egress allowlist, gitleaks/semgrep in CI (mandatory).
- DoD: a new developer/agent can clone, `up`, and pass CI in <30 min.

**Phase 1 — Command center + document core + model gateway** (`[BUILD NOW]`)
- Deliverables: API, auth+MFA, project/document CRUD, ingestion→malware→OCR→index,
  document view with overlays, RAG query with citations, model gateway (1 cloud +
  1 local) with cost tracking, cost view, error queue.
- Dependencies: Phase 0.
- Acceptance: upload a scanned PDF → OCR'd, viewable, page-addressable; ask a
  question → answer cites a real page span; every model call logged with cost;
  confidential doc routes to local model per policy.
- Risks: OCR quality. Mitigation: confidence thresholds + review queue.
- Security: data-classification gate live; malware scan mandatory; auth+MFA.
- DoD: one project completed as "documents in, cited answers out," no fabrication.

**Phase 2 — Workflows, agents, approvals, evidence, monitoring** (`[BUILD NOW/NEXT]`)
- Deliverables: Temporal task graph; Commander/Planner/Research/Document agents;
  approval queue; full evidence view + contested handling; monitoring dashboards;
  kill switch; agent budgets.
- Dependencies: Phase 1.
- Acceptance: an agent completes a multi-step task with checkpoints; killing it
  mid-run leaves consistent state; every external/irreversible action is gated;
  a forced failure appears in the error queue and alerts.
- Risks: agent runaway. Mitigation: budgets, sandbox, kill switch, circuit
  breakers.
- Security: capability sandboxing + default-deny authz mandatory.
- DoD: no agent can act externally without an approval; all actions audited.

**Phase 3 — Landman document intelligence + structured title** (`[BUILD NOW after 2]`)
- Deliverables: instrument classification, span extraction, entity resolution,
  chain-of-title builder, deterministic WI/NRI/royalty math, gap/conflict
  detection, runsheet + draft ownership report, examiner review queue.
- Dependencies: Phase 2, `libs/title-math` (port `horizon/`).
- Acceptance: on a synthetic county set, chain builds; interests balance to 100%
  or the tract is flagged contested; every number click-throughs to evidence; a
  seeded gap is detected; **no ownership number renders without evidence.**
- Risks: fabricated conclusions. Mitigation: Part 7 controls; human review gate.
- Security: draft/disclaimer labeling; release gated by human.
- DoD: one real title project produces a reviewer-traceable draft with zero
  unevidenced facts.

**Phase 4 — Tournaments, advanced verification, automation** (`[BUILD LATER]`)
- Deliverables: tournament service + rubric, verification agents, red-team judge,
  model-router learning from stored results, visual automation builder over vetted
  workers.
- Dependencies: Phase 2–3.
- Acceptance: tournament scores are reproducible; grounded-only claims survive;
  an intentionally wrong majority is beaten by an evidenced minority; router
  improves on a golden set in shadow mode.
- Risks: cost blow-up. Mitigation: budgets, tiered escalation.
- Security: prompt-leakage sanitization.
- DoD: tournaments measurably reduce error rate on a labeled set vs single model.

**Phase 5 — Business ops, integrations, mobile, voice** (`[BUILD LATER]`)
- Deliverables: scoped connectors (email/cal/files/CRM/accounting, read-first),
  reporting, mobile (read/approve/pause), voice (dictation/query).
- Dependencies: Phase 2 (approvals), Phase 1 (auth).
- Acceptance: no external write without approval; mobile can approve+pause but not
  admin; connectors run least-scope.
- Risks: data exfiltration via connectors. Mitigation: DLP + egress allowlist +
  approval on every send.
- Security: per-connector scopes mandatory.
- DoD: an email drafts but never sends without a human tap.

**Phase 6 — Safe self-improvement, scaling, advanced autonomy** (`[BUILD LATER]`)
- Deliverables: nightly improvement workflow (proposals + draft PRs), shadow-mode
  extraction/prompt evaluation, bounded router auto-tuning, multi-node scale-out
  if needed.
- Dependencies: all prior; strong eval sets.
- Acceptance: no production change lands without tests + human merge; shadow
  proposals beat baseline before surfacing; audit shows every change's origin.
- Risks: silent drift. Mitigation: everything through PR+CI+human; never touch
  math/policy/audit autonomously.
- Security: self-improvement cannot alter safety controls.
- DoD: the system improves its own prompts/routing measurably while every change
  is human-approved and reversible.

---

## Part 18 — First 30 Build Tasks (in order)

Format per task: **Name — Purpose | Modules | Deps | Acceptance | Tests |
Security.**

1. **Repo skeleton + CI** — enforce structure/quality gates | root, `.github` |
   — | CI runs lint/type/test/security on PR | pipeline smoke | gitleaks+semgrep
   on.
2. **Docker Compose base** — one-command local stack | `infra` | 1 | `up` starts
   Postgres/MinIO/NATS | health checks | services on private net, localhost only.
3. **DB schema + Alembic** — core tables (Part 15) | `migrations`,`libs/schemas`
   | 2 | migrate up/down clean | migration test | provenance FKs NOT NULL.
4. **Secrets vault wiring** — no secrets in repo | `infra`,`libs/policy` | 2 |
   secret fetched at runtime, none in env files | leak scan | rotation supported.
5. **Object store + WORM** — immutable originals | `services/ingestion` | 2 |
   overwrite fails; hash-addressed | immutability test | object-lock on.
6. **Audit log (hash-chained)** — tamper-evident trail | `libs/observability`,
   `services/api` | 3 | events chain verifies | chain-tamper test | append-only.
7. **API skeleton + authN/MFA** — the only entry | `services/api` | 3,4 | login
   +TOTP; unauth denied | auth tests | default-deny.
8. **Policy engine (authz)** — capability checks | `libs/policy` | 7 | denied
   action blocked+audited | policy tests | default deny.
9. **Backup/restore scripts** — data safety | `scripts` | 3,5 | round-trip
   restore | restore test | encrypted target.
10. **Malware scan + type verify** — safe ingestion | `services/ingestion` | 5 |
    bad file quarantined before parse | eicar test | scan before parse.
11. **Ingestion workflow** — hash→scan→store→event | `services/ingestion`,
    `services/workflow` | 5,10 | dup bytes → no 2nd write | idempotency property |
    no path traversal.
12. **OCR service (interface + Tesseract)** — text+geometry | `services/ocr` | 11
    | scanned PDF → text+bbox+conf | golden OCR | provider-neutral, local default.
13. **Document version model** — versioned derived layer | `services/ocr`,
    `libs/schemas` | 3,12 | reprocess → new version, old kept | version test | no
    overwrite.
14. **Layout-aware chunking** — anchored chunks | `services/extraction` | 12 |
    chunks carry page+bbox | anchor test | —.
15. **Embeddings + pgvector index** — semantic search | `services/extraction` |
    3,14 | similar chunk retrieved | recall test | local embeddings for confidential.
16. **Model gateway + cost** — provider-neutral calls | `services/model-gateway`
    | 4,8 | call logged with tokens/cost; fallback works | gateway tests |
    data-class gate enforced.
17. **Data-classification policy** — what may leave box | `libs/policy`,
    `services/model-gateway` | 16 | confidential → local only | routing test |
    mandatory.
18. **RAG query w/ citations** — cited answers | `services/api`,
    `services/extraction` | 15,16 | answer cites real span; no span → "unknown" |
    citation test | no cross-project leak.
19. **Command center shell** — one UI screen | `apps/command-center` | 7,18 |
    login→project→ask→cited answer | e2e | client of API only.
20. **Document viewer + overlays** — evidence UX | `apps/command-center` | 13,19 |
    click fact → jumps to bbox | e2e | —.
21. **Cost view + budgets** — spend control | `services/api`,`apps` | 16 | budget
    alert fires | budget test | —.
22. **Error queue** — no silent failure | `services/api`,`apps` | 6 | forced
    failure appears | failure test | —.
23. **Temporal integration** — durable task graph | `services/workflow` | 2,11 |
    kill mid-run → consistent resume | replay test | activity boundary checks.
24. **Approval queue + gates** — human control | `services/api`,`apps` | 8,23 |
    gated action blocks until approved | gate test | every external/irreversible
    action.
25. **Sandbox tool runtime** — capability-scoped exec | `libs/policy`,
    `services/workflow` | 8,23 | tool w/o grant denied; no ambient net | escape
    test | gVisor/allowlist egress.
26. **Commander + Planner agents** — intent→plan | `agents`,`services/workflow` |
    23,24 | ambiguous intent → asks; cyclic plan rejected | plan tests | no side
    effects in planning.
27. **Research + Document agents** — cited answers, extraction | `agents` | 18,26
    | proposes facts with evidence; no evidence → abstains | agent evals | read-only
    to persist needs approval.
28. **Entity resolution + dedupe** — canonical entities | `services/extraction` |
    3,27 | near-dup flagged not deleted; merge reversible | resolution test | —.
29. **`libs/title-math` (port horizon)** — exact interests | `libs/title-math` |
    3 | WI=100% invariant; NRI≤WI; property-tested | property+golden | pure, no I/O.
30. **Chain-of-title + gap/conflict + draft report** — landman core |
    `services/title-engine` | 28,29 | balances or flagged contested; seeded gap
    detected; **no unevidenced number renders** | title e2e | draft/disclaimer;
    human release gate.

---

## Part 19 — Decisions and Warnings

**10 most important design decisions**
1. Evidence ledger (not any model) is the source of truth.
2. Deterministic math/validation; LLMs propose, never conclude.
3. Durable workflow engine (Temporal) as the spine.
4. Postgres + pgvector as one transactional store (colocated provenance).
5. Provider-neutral, policy-aware model gateway with data-classification routing.
6. Capability-scoped sandboxed tools; no raw shell/network to agents.
7. Append-only, hash-chained audit; soft-delete + WORM originals.
8. Human approval on all irreversible/external actions.
9. Monorepo with enforced module boundaries.
10. One working vertical slice before breadth.

**10 most dangerous mistakes**
1. Letting "models agreed" stand in for evidence.
2. Using an LLM for interest math.
3. Giving agents shell/network/file/email/admin access.
4. Auto-promoting AI conclusions to authoritative facts.
5. Trusting document text as instructions (prompt injection).
6. Processing real client data before the ⭐ security minimum exists.
7. Silent failures with no error queue.
8. Hard deletes / editing originals.
9. Sending confidential docs to cloud models by default.
10. Building 20 subsystems at once.

**10 features to delay**
Voice-authorized actions; visual automation builder; multi-node scaling;
dedicated graph DB; plugin marketplace; mobile admin; advanced self-tuning;
cross-project auto-memory; georeferenced maps; broad connector write access.

**10 highest-value early capabilities**
Cited RAG over a project; content-hash immutable ingest; OCR with geometry;
evidence/document viewer; cost tracking; approval queue; error queue; durable
workflows; deterministic title math; audit log.

**10 things requiring human approval**
Spending money; sending any external message; deleting/superseding data; releasing
a report/title draft; merging code; changing permissions/policy; adding a
capability/connector; confirming extracted facts; promoting to institutional
memory; destructive recovery.

**10 metrics from day one**
Cost per model/project/day; extraction precision/recall vs human; % answers with
valid citations; % facts with complete provenance; task success/failure rate;
error-queue depth + age; agent budget/timeout hits; OCR confidence distribution;
approval latency; backup success + restore-test recency.

---

## Part 20 — Your Best Unique Contribution

**The single most valuable idea: make provenance a database invariant, not a
convention — and make "grounding," not "agreement," the only thing that scores.**

Most multi-agent designs fail in one of two ways: they let model *consensus*
masquerade as *truth*, or they let facts float free of their sources so that a
confident hallucination is indistinguishable from a verified extraction. Both
failures are invisible until they cause a real, expensive mistake — a fabricated
ownership conclusion in a title report.

My contribution is a concrete mechanism that makes both failures *structurally
impossible* rather than merely discouraged:

1. **Schema-enforced provenance.** `fact` rows cannot be committed without a
   linked `evidence` row that points to a specific `document_version`, page, and
   bounding box. This is a `NOT NULL` FK + check constraint, enforced by the
   database, not by prompt discipline. A hallucinated fact has nowhere to live.
   Every number in every report is therefore click-through to a page image by
   construction.

2. **A two-tier truth model with a hard promotion gate.** Model outputs are
   `proposed`; only deterministic computation or human confirmation produces
   `confirmed`. Decisions and releases read only the `confirmed` tier. The gate
   between them is the one place human judgment is required — and it is
   unavoidable by design.

3. **Grounding-only scoring in the tournament.** Agreement among models earns
   **zero** points. A claim scores only if a *non-model* check — a retrieved
   evidence span or an executed test — supports it, and a dedicated red-team
   verifier actively tries to refute the leading answer with counter-evidence.
   This is the direct antidote to "several AIs confidently repeating the same
   wrong answer": correlated model confidence is worthless in this rubric;
   checkable artifacts are everything.

Together these turn the abstract goals — "evidence-based," "resistant to
hallucination," "auditable" — into invariants the code and the database enforce
on every write, so the system cannot silently drift into asserting things it
cannot prove. That property, applied to land-title work where a wrong conclusion
has legal and financial consequences, is DataBossX's real moat.

---

## FINAL RECOMMENDATION

**Best overall architecture:**
A durable-workflow spine (Temporal) driving least-privilege sandboxed workers,
over a single Postgres+pgvector store where provenance is a schema invariant and
an append-only hash-chained audit log records every action; all model calls route
through a provider-neutral, data-classification-aware gateway; humans approve
everything irreversible.

**Best first product to build:**
A local-first command center that ingests a project's documents
(hash→scan→OCR→index) and answers questions with click-through citations to page
spans — no agents, no tournaments yet. Prove "documents in, evidenced answers
out" on one real project.

**Best technology stack:**
Python/FastAPI + TypeScript/Next.js (Tauri desktop shell) + PostgreSQL 16 with
pgvector + Temporal + NATS/Redis + Docker Compose + Ollama/vLLM local models +
provider-neutral cloud gateway + Tesseract/PaddleOCR + Vault + OTel/Prometheus/
Grafana/Loki + pytest/hypothesis/Playwright.

**Most important security control:**
Capability-scoped, sandboxed tool execution with default-deny egress + a
data-classification gate on the model gateway — i.e., agents can never take an
unapproved external action or send confidential data off-box.

**Most important data design decision:**
Provenance as a `NOT NULL`/check-constraint invariant: no fact exists without a
link to a specific source span; two-tier proposed→confirmed truth with a human/
deterministic promotion gate.

**Best Codex and Cursor workflow:**
Spec-first, one-module-per-branch, Codex implements to a typed interface with
tests-first and a hard out-of-scope boundary enforced by CI/CODEOWNERS; Cursor
reviews (never merges) with the adversarial review prompt; humans approve every
merge; security/math/migration changes require an extra human reviewer.

**Biggest technical risk:**
Fabricated conclusions — LLM output treated as fact without evidence or
deterministic confirmation (especially in title math). Mitigated by schema-
enforced provenance + pure deterministic math + human gates.

**Biggest operational risk:**
Scope explosion — attempting all 20 subsystems at once and finishing none.
Mitigated by the phased roadmap forcing one working vertical slice first.

**Most valuable early feature:**
Cited RAG over a single project's documents with a click-through evidence viewer.

**Feature that should be delayed:**
Voice-authorized actions and the visual automation builder (and all connector
*write* access) — high risk, low early value.

**One idea other AIs may miss:**
Score grounding, not agreement: make model consensus worth zero points and let
only checkable artifacts (evidence spans, executed tests) earn score — with a
red-team verifier that tries to refute the leader. Combined with schema-enforced
provenance, this makes confident-but-wrong consensus structurally unable to
become a "fact."

**Confidence in this proposal, 0–100:**
82 — high confidence in the architecture, provenance model, security posture, and
phasing; lower confidence on exact third-party choices (OCR quality on real
county records, local-model quality for confidential inference, and Temporal's
operational overhead for a single operator), which are flagged `[UNCERTAIN]` and
should be validated in Phase 1.

END OF RESPONSE — AI NAME: Claude Code
