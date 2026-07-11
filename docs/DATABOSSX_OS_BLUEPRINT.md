# DataBossX Operating System

Status: architecture decision and execution contract  
Date: 2026-07-11  
Primary outcome: evidence-grounded title research and report production

## Executive decision

DataBossX should not be a collection of chatbots or a model switchboard. It
should be a **local-first work operating system**:

```text
Operator intent
  → one policy-aware orchestrator
  → durable task graph
  → specialized, least-privilege workers
  → immutable evidence and derived artifacts
  → deterministic title calculations and validation
  → licensed human review
  → versioned report release
```

The immediate goal is not to connect every cloud account. It is to complete one
real title project end to end without fabrication, evidence loss, workbook
damage, or an unverifiable conclusion. Connectors and broader company memory
then grow around that proven core.

## What exists now

| Asset | Keep and reuse | Required change |
| --- | --- | --- |
| `grocery_report_pipeline.py` | A–I workflow, inventory, classification, reconciliation, validation, report artifacts | Split into workers; remove original-file moves; replace report-level facts with field-level evidence |
| `horizon/` | Exact fraction math, instrument chaining, review artifacts, validation, workbook repair/versioning | Make evidence field-level; disable automatic production repair and deletion |
| `doto_image_commander/` | County acquisition, queue concepts, OCR/vision flow, costs, audit | Move to the common task graph and provider-neutral OCR interface |
| `mineral_deal_room/` | Vite UI shell, review/evidence/audit patterns | Replace static sample data with the canonical API |
| `backend/` and `frontend/` | Only small UI/API ideas | Retire after migration; current backend contains mock OCR and unsafe broad CORS |
| PR #26, DataBoss Title Factory | Strongest source-hash, OCR geometry, candidate archive, resume, control workbook, and workbook-integrity foundation | Review, merge, then split its large core into canonical services |
| PR #25, Horizon report generator | Export and Drive ideas only | Do not establish it as a second title authority; reimplement useful adapters on the canonical model |

Relevant work:

- Title Factory PR: https://github.com/DataBossX/DataBoss/pull/26
- Generic Horizon Report PR: https://github.com/DataBossX/DataBoss/pull/25
- Title Factory cloud run: https://cursor.com/agents/bc-019f4f7e-60b4-7932-81a1-da3e1f54ee63
- Section 31 cloud run: https://cursor.com/agents/bc-019f3443-a4fe-7a25-a3b0-a932ea889bf5
- Horizon cloud run: https://cursor.com/agents/bc-019f32dd-b81a-709d-b8c1-63f73d08295a

None of the cloud runs had the real private title corpus. Section 31 analysis
therefore remained at 0% evidentiary completion. PR #26 built and tested the
local evidence machinery but did not produce a completed Section 32 report.

## Product boundaries

### The system is

- A work coordinator, evidence ledger, research assistant, calculation engine,
  review queue, and report-production system.
- A searchable inventory of assets the operator has authorized it to index.
- A provider-neutral router that chooses capabilities under policy, quality,
  privacy, cost, and latency constraints.
- A human-supervised tool builder that turns repeated work into reviewed,
  versioned tools.

### The system is not

- An autonomous title examiner, attorney, abstractor, or source of legal advice.
- A mechanism for model agreement to substitute for documentary evidence.
- A cloud crawler with unrestricted access to every account.
- A system that silently edits originals, client templates, or released reports.
- A reason to send confidential source documents to every available model.

For Oklahoma work, examination of an abstract for a marketability opinion is
legal work requiring a licensed attorney. The software may organize evidence,
extract candidates, compute exact interests, and prepare draft work product; it
must not label an unreviewed model output as a title opinion or certified
abstract. See:

- https://www.okbar.org/barjournal/june-2024/oklahoma-title-examination-standards-providing-guidance-since-1946/
- https://oklahoma.gov/content/dam/ok/en/abstractors/documents/statutes-rules/Title%201%20-%20Oklahoma%20Abstractors%20Act%20082924.pdf

## Non-negotiable rules

1. **Source controls.** A model, prompt, spreadsheet, prior report, or majority
   vote cannot overrule the source image.
2. **No fabrication.** Unknown, missing, unreadable, inapplicable, inferred,
   assumed, and externally researched are distinct values.
3. **Field-level provenance.** Every material value links to a source hash and
   page/sheet/row plus bounding region or character offsets where possible.
4. **Immutable originals.** Inventory and vault operations copy and hash; they
   never delete, rename, move, or overwrite originals.
5. **Append-only derivation.** OCR, extraction, reconciliations, reports, and
   corrections create new versions.
6. **Exact arithmetic.** Mineral and working interests use integer
   numerator/denominator values; display decimals are derived.
7. **Conflicts remain conflicts.** Models may detect them; a qualified human
   resolves material conflicts.
8. **Approval binds hashes.** Any input, policy, tool, prompt, or output change
   invalidates the previous approval.
9. **Least privilege.** Workers receive only the inputs, tools, scopes, and
   egress required for one leased task.
10. **One writer.** Only the orchestrator commits state transitions and creates
    downstream tasks.
11. **No production write by default.** External writes require an exact,
    expiring human approval of destination and payload hash.
12. **Complete audit.** A released artifact must be reproducible from its source
    snapshot, tool versions, route decisions, review decisions, and event log.

These controls align with NIST AI 600-1's emphasis on governance, provenance,
testing, incident disclosure, and defined human oversight:
https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence

## Target architecture

Build a Python modular monolith first:

- FastAPI control API, bound to loopback by default
- SQLite in WAL mode with numbered migrations and FTS5
- content-addressed local vault: `runtime/vault/sha256/<prefix>/<hash>`
- one orchestrator process and one or more local worker processes
- Pydantic command, event, and artifact contracts
- one Vite/React TypeScript interface
- an outbox table for reliable events
- provider interfaces at every external boundary

Do not add Redis, Celery, Kafka, Kubernetes, a vector database, or a multi-agent
framework until measured concurrency or retrieval requirements justify them.

```text
┌──────────────────────────── local trust boundary ────────────────────────────┐
│ UI → Control API → Policy engine → Orchestrator → Task graph                │
│                      ↓                 ↓                                     │
│              Approval ledger       Worker leases                            │
│                      ↓                 ↓                                     │
│  SQLite/FTS5 ← Event outbox ← Outcomes → Evidence/claim graph               │
│       ↓                                  ↓                                   │
│  Search index                  Content-addressed vault                       │
│                                          ↓                                   │
│                Title engine → review → report/workbook audit                 │
└──────────────────────────────────────────────────────────────────────────────┘
       ↑ read-only snapshots                       ↓ policy-gated calls
 Local/Drive/Dropbox/GitHub/HF/chat exports        Model and research APIs
```

Proposed code layout is recorded in
`docs/architecture/databossx-os.build-plan.json`.

## Canonical domain

### Evidence and memory

- `Project`: bounded work with jurisdiction, policy set, confidentiality, and
  lifecycle.
- `SourceConnection`: authorized provider/root and read/write capabilities;
  stores a credential reference, never a credential.
- `SourceSnapshot`: provider cursor/version, scan time, completeness, and
  manifest hash.
- `Asset`: logical item; an `AssetVersion` records locator, provider version,
  byte hash, size, custody time, and immutable vault path.
- `DerivedArtifact`: hash-addressed child of one or more asset versions with a
  versioned recipe.
- `EvidenceSpan`: exact source snippet and coordinates tied to one asset
  version.
- `Claim`: typed subject/predicate/value candidate with value state and
  immutable revisions.
- `ClaimSupport`: evidence edge and support-rule version.
- `Conflict`: competing claims, materiality, and human resolution.

### Work

- `WorkflowDefinition` and `Run`
- `Task`, `TaskDependency`, `TaskAttempt`, and `TaskLease`
- `WorkerCapability` and `ToolDefinition`
- `ModelRouteDecision` and `ToolRun`
- `ReviewGate`, `ReviewDecision`, and `Approval`
- `Artifact` and immutable `ArtifactVersion`
- append-only `AuditEvent`

### Title extensions

- `TitleProject`, `Jurisdiction`, `SearchScope`, `Tract`, and `LegalDescription`
- `Instrument`, `InstrumentParty`, `RecordingReference`, and `InstrumentClaim`
- `ChainLink`, `InterestLedgerEntry`, `Lease`, `Assignment`, `Well`, and `HBPFact`
- `TitleException`, `CurativeItem`, `ExaminerIssue`, and `MissingDocument`
- `WorkbookCandidate`, `WritableRangeApproval`, and `WorkbookIntegrityAudit`

Persist exact interests as numerator and denominator. Never convert a display
decimal back into a legal calculation.

## Title Factory workflow

### Project lifecycle

```text
DRAFT
→ INVENTORY_REVIEW
→ EVIDENCE_LOCKED
→ PROCESSING
→ EXAMINER_REVIEW
→ APPROVED_FOR_EXPORT
→ EXPORTED_CANDIDATE
→ RELEASED
```

Required flow:

1. Register a local project folder as read-only.
2. Inventory every source and candidate; hash bytes and record custody.
3. Review duplicates, missing categories, templates, prior reports, and source
   scope before locking evidence.
4. Copy source bytes into the append-only vault and verify both hashes.
5. Render documents into page images without changing source files.
6. Run deterministic OCR first; use vision only where policy permits.
7. Run independent extraction passes that return schema-valid candidate
   envelopes, never direct database writes.
8. Reject provenance that does not cover the semantic field region.
9. Reconcile identical source-supported claims; open conflicts for material
   disagreement.
10. Normalize parties, instruments, legal descriptions, and tracts while
    preserving original text.
11. Build instrument, ownership, lease, assignment, and well/HBP chains.
12. Compute interests exactly and test conservation, over-conveyance,
    duplicates, gaps, and legal-description mismatches.
13. Present image, OCR, claim, competing candidates, and chain impact together
    in the examiner review queue.
14. Generate a new client candidate and a separate control workbook.
15. Compare OOXML parts, formulas, styles, names, merges, validations, print
    settings, links, drawings, images, charts, and macros against the template.
16. Bind approval to the candidate hash and full input manifest.
17. Release a new immutable version; never overwrite the candidate or template.

The system must block release if any material claim lacks source support, a
material conflict is unresolved, exact interests fail validation, the source
changed after inventory, or workbook integrity failed.

## Inventory and company memory

Inventory is a connector framework, not one giant copy operation.

Connector order:

1. Local folders and attached drives
2. GitHub repository metadata and approved content
3. Google Drive
4. Dropbox
5. exported ChatGPT/Claude/Cursor/Codex workspaces
6. Hugging Face repository metadata
7. approved websites and county/public-record sources

Each connector must support dry-run, bounded roots, incremental cursors, stable
provider versions, checksums where available, retries, rate limits, and
read-only mode. Store metadata first. Copy content only when policy and project
scope require it.

- Google Drive should use `drive.file` with user-selected files wherever
  possible, not account-wide access:
  https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- Drive change notifications are signals; query the change feed using the
  stored page token to obtain details:
  https://developers.google.com/workspace/drive/api/guides/manage-changes
- Dropbox should use a single app folder and minimum
  `files.metadata.read`/`files.content.read` scopes:
  https://www.dropbox.com/developers/reference/webhooks
- GitHub should use repository-scoped fine-grained credentials with
  `contents:read` and `metadata:read`:
  https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

Search starts with metadata filters and FTS5. Add embeddings only after a
versioned retrieval benchmark proves improvement over lexical and structured
search. Every search answer cites asset versions and exact evidence spans.

## Task engine

Task states:

```text
PLANNED → BLOCKED | READY → LEASED → RUNNING
RUNNING → SUCCEEDED | WAITING_HUMAN | FAILED_RETRYABLE | FAILED_TERMINAL
FAILED_RETRYABLE → READY
WAITING_HUMAN → READY | FAILED_TERMINAL
```

Every task has:

- immutable input manifest and idempotency key
- required capability and policy
- dependency conditions
- lease owner, expiry, heartbeat, attempt, and budget
- schema-validated outcome and output manifest
- correlation/causation IDs

Workers cannot claim success by prose. They return a typed outcome. The
orchestrator validates it, records events, and alone decides which tasks become
ready. Bounded retries, circuit breakers, token/cost limits, and dead-letter
review prevent runaway loops.

## Model routing

Do not hardcode “provider X is always best.” Models change. Route a capability
request using a versioned model catalog and evaluation results.

Hard policy filters run first:

1. confidentiality and allowed egress
2. required modality and context size
3. structured-output/tool support
4. jurisdiction or data-residency restrictions
5. model/provider health

Then rank eligible routes using task-specific quality, evidence-grounding rate,
schema-validity rate, latency, and expected cost. Deterministic inventory,
hashing, title math, chain rules, and workbook comparison never route to an LLM.

Every route records considered candidates, rejection reasons, selected
provider/model/version, prompt/tool versions, input/output hashes, tokens,
latency, cost, retries, and evaluation result. A second model may challenge a
candidate, but agreement is not evidence.

## Self-builder, safely

The self-builder is a governed improvement backlog:

1. Detect repeated manual steps from task and review events.
2. Propose a tool with expected benefit, examples, permission manifest, JSON
   schemas, tests, rollback, and owner.
3. Generate it in an isolated branch/sandbox.
4. Run unit, golden, adversarial, secret, license, and dependency checks.
5. Require human code review and explicit enablement.
6. Canary on synthetic or de-identified projects.
7. Version and monitor it; retire it if quality regresses.

It may propose and build. It may not deploy itself, expand its permissions,
change release gates, edit its own audit history, or run on client evidence
without approval.

## Command Center

One Vite application should expose:

- Projects and release status
- Task graph and worker health
- Evidence viewer with source-region highlights
- Claims, conflicts, and examiner review queue
- Title chains and exact-interest ledger
- Searchable company memory with citations
- Artifacts and workbook-integrity reports
- Connector health and inventory coverage
- Models, route decisions, costs, and evaluations
- Tool registry and improvement proposals
- Append-only audit timeline
- Policies, approvals, users, and settings

DataBossX.com can later provide authenticated coordination and client-safe
views. Confidential evidence processing, county credentials, and Excel
automation remain local unless a project policy explicitly authorizes remote
processing.

## Build sequence

### Phase 0 — contain the credential incident

- Rotate all credentials listed in `SECURITY.md`.
- Merge current-tree secret scanning and local hooks.
- Decide with all collaborators whether to rewrite history.
- Replace broad credentials with scoped connector identities.

Gate: every exposed credential is revoked; current tree scans clean.

### Phase 1 — prove the title vertical slice

- Review and merge PR #26.
- Run it on the real Windows Section 32 corpus.
- Record inventory completeness, OCR coverage, unresolved conflicts, chain
  gaps, workbook fingerprint, and examiner decisions.
- Port Horizon exact-interest and instrument-chaining logic into that evidence
  workflow.

Gate: one real candidate report is traceable field by field, all exact math
passes, workbook integrity passes, and a qualified human approves the exact
artifact hash.

### Phase 2 — trusted kernel

- Introduce the canonical package, migrations, vault, event ledger, task graph,
  policy engine, and local connector.
- Migrate PR #26 checkpoints and Grocery stages into typed tasks.
- Expose the API and build the evidence/review UI.

Gate: crash/restart is idempotent; originals cannot be mutated through any API;
the audit log reconstructs every artifact.

### Phase 3 — memory and recon

- Add GitHub, Drive, Dropbox, chat-export, and Hugging Face metadata connectors
  in that order.
- Build FTS5 and structured search, dedupe, source maps, ownership/retention
  labels, and citation rendering.

Gate: repeated scans are incremental and read-only; every result cites a stable
source version; connector scope tests prove least privilege.

### Phase 4 — routing and worker catalog

- Add provider-neutral OCR, vision, extraction, research, QC, and export
  capabilities.
- Build evaluation sets from reviewed corrections.
- Add budget, privacy, and fallback policies.

Gate: provider changes require no workflow changes; remote processing is
technically impossible under local-only policy.

### Phase 5 — migrate DOTO and deal workflows

- Move DOTO acquisition into the common task graph with explicit cost approval.
- Connect the deal-room UI to canonical projects, evidence, tasks, and reviews.
- Retire product-specific queues and the mock backend.

Gate: one orchestrator, one evidence model, one review system, one audit stream.

### Phase 6 — governed tool factory and client portal

- Add improvement proposals, sandboxed builds, canaries, and versioned tools.
- Add client-safe report views and delivery workflows.

Gate: no tool can self-enable or expand permission; client views expose only
approved artifacts and redacted audit information.

## Release acceptance tests

- Source replacement after inventory blocks all downstream approval.
- Path traversal, symlinks, malformed archives, and decompression bombs are
  contained.
- Prompt injection in a deed or webpage cannot select tools or change policy.
- Unsupported fields remain null and generate review work.
- Conflicting candidates cannot be resolved by confidence or majority vote.
- Duplicate instruments do not double-count interests.
- Property-based tests preserve exact interest conservation.
- Lease/assignment/well links require instrument and legal support.
- Interrupted and uninterrupted runs produce equivalent manifests.
- Stale task leases and stale approvals cannot publish output.
- Workbook modifications outside approved ranges fail integrity checks.
- Secrets do not enter prompts, logs, events, artifacts, or browser bundles.
- Connectors cannot write, delete, share, or access roots outside their grants.
- Every released value opens its source region in two actions or fewer.

## Next operator action

Do these in order:

1. Rotate the exposed keys in `SECURITY.md`.
2. Review and merge PR #26; do not merge PR #25 as a competing engine.
3. On the Windows machine that contains the real Section 32 files, run PR #26's
   setup, tests, and inventory only.
4. Review the source manifest before allowing OCR or extraction.
5. Complete the real evidence-to-candidate flow and licensed examiner review.
6. Use the resulting failures and corrections as the golden acceptance corpus
   for the trusted kernel—not synthetic assumptions.

The first success metric is not “number of agents.” It is:

> one released title work product whose material values, calculations,
> conflicts, reviewer decisions, and workbook changes are completely
> attributable and reproducible.
