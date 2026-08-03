# ADR 0008: Provider-neutral Agent Lab

- Status: proposed
- Date: 2026-08-03
- Scope: public-safe architecture and synthetic evaluation only
- Decision owner: DataBossX operator
- Related: `docs/DATABOSSX_OS_BLUEPRINT.md`, issue #78, draft PR #82

## Decision

DataBossX remains the only authority for projects, task state, approvals, leases,
fences, evidence, audit events, artifacts, and release decisions.

Third-party agent systems and model runtimes may be attached only as
least-privilege workers or design tools. They never become a second queue,
scheduler, policy engine, receipt ledger, source of truth, or workbook writer.

The integration boundary is:

```text
DataBossX task envelope
  -> policy and data-classification gate
  -> capability adapter
  -> isolated provider or local worker
  -> schema-validated candidate outcome
  -> provenance and evaluation
  -> DataBossX orchestrator decision
```

A worker result is a candidate. It cannot activate a command, issue a lease or
fence, change canonical state, write a protected workbook, promote an artifact,
or remove a release hold.

## Tool decisions

### Flowise: adopt for the Agent Lab only

Use Flowise as an optional visual workflow prototyper, demo surface, and
debugging aid for synthetic or de-identified tasks.

Allowed:

- prototype extraction, research, and review flows;
- compare prompt and model routes;
- visualize branching and human-review points;
- export a versioned flow definition for evaluation;
- call a DataBossX test adapter with synthetic fixtures.

Prohibited:

- polling or owning the DataBossX queue;
- storing client evidence or production credentials;
- direct Google Drive, county, workbook, release, or deployment writes;
- issuing approvals, WriterACKs, leases, fences, STARTs, or terminals;
- treating Flowise execution history as the canonical audit log.

Adoption gate:

1. Pin the Flowise image and dependency digest.
2. Bind to loopback or an isolated private network.
3. Disable public sharing and unneeded telemetry.
4. Use synthetic fixtures and fake credentials.
5. Export and hash the flow definition.
6. Pass schema, provenance, prompt-injection, egress, timeout, retry, and cost tests.
7. Reimplement any promoted workflow through the canonical DataBossX capability
   contract, or keep Flowise permanently lab-only.

Flowise is not added as a required production dependency.

### LLaMA-Factory: defer production use, approve a gated training lab

LLaMA-Factory is useful when reviewed corrections demonstrate that prompting,
retrieval, deterministic rules, and model routing cannot meet a measured
task-specific quality target.

Allowed future uses:

- LoRA or QLoRA experiments for document classification, field extraction,
  tool-call formatting, and reviewer-assist ranking;
- synthetic, public, licensed, or irreversibly de-identified training data;
- local evaluation and adapter packaging.

Prohibited:

- training on raw client documents by default;
- learning directly from unreviewed model output;
- automatic promotion of a trained adapter;
- using model confidence as title evidence;
- replacing exact interest math, chain rules, or source verification.

Training gate:

1. Define the capability, baseline, acceptance metric, and failure cost.
2. Build a versioned dataset solely from reviewed examples with provenance,
   license, retention, and contamination records.
3. Create fixed train, validation, and untouched test splits.
4. Benchmark prompting and retrieval first.
5. Train only in an isolated lab with no production credentials.
6. Run golden, adversarial, memorization, privacy, calibration, and regression
   evaluations.
7. Package the adapter with base-model identity, dataset manifest hash, config,
   code revision, license, metrics, limitations, and rollback.
8. Require explicit human enablement in the model catalog.

No fine-tuned model may write canonical facts. It returns candidates with source
locators for deterministic validation and human review.

### AMD Ryzen AI Halo: benchmark before purchase

A 128 GB Ryzen AI Max+ 395 system is a credible optional local worker for private
inference and model experiments. It is not a prerequisite for DataBossX and is
not a control-plane appliance.

Use only after a repeatable benchmark shows that the existing Windows machine
cannot meet privacy, latency, throughput, or cloud-cost targets.

A pilot worker must:

- run outbound-only;
- hold no Drive, GitHub, county, or release credentials beyond its leased task;
- receive immutable input manifests and return immutable output manifests;
- heartbeat, checkpoint, expire, and stop under the canonical task engine;
- expose health, model, context, tokens, latency, power, memory, and failure
  telemetry;
- remain unable to mutate canonical state directly.

Purchase gate:

1. Record the current machine specification and baseline.
2. Test representative OCR, vision, 8B to 32B inference, long-context, and batch
   extraction workloads.
3. Compare quality, tokens per second, queue latency, energy, setup effort,
   reliability, and three-year total cost against cloud and existing hardware.
4. Purchase only if the measured gain clears a documented threshold and the
   workload is sustained.

## Preferred supporting stack

| Need | Preferred approach | Decision |
| --- | --- | --- |
| Durable orchestration | DataBossX SQLite task graph, outbox, leases, fences | canonical |
| Visual flow design | Flowise in isolated Agent Lab | pilot |
| Cloud model gateway | Existing provider-neutral adapter; LiteLLM may remain an implementation detail | keep bounded |
| Local desktop inference | LM Studio or Ollama behind an OpenAI-compatible adapter | pilot |
| Linux GPU serving | vLLM or SGLang only when benchmarked hardware exists | defer |
| Fine-tuning | LLaMA-Factory isolated training lab | defer until gate |
| Evaluation | Versioned pytest/golden/adversarial harness with exact manifests | build now |
| Observability | Local structured logs, metrics, traces, and cost ledger | build now |
| Workflow automation | DataBossX task graph | do not add n8n, LangGraph, Prefect, or Temporal as another authority |
| Secrets | OS credential store or approved secret manager via references | required |
| Retrieval | Structured filters plus FTS5 before embeddings | keep |
| Vector search | Add only after a versioned benchmark proves value | defer |

## Capability contract

Every external worker invocation must record:

- project and task identifiers;
- immutable TaskEnvelope and input-manifest hashes;
- classification and allowed-egress decision;
- provider, model, revision, adapter, prompt, tool, and policy versions;
- requested capability and JSON input/output schemas;
- time, token, cost, context, retry, and concurrency budgets;
- lease, fence, heartbeat, expiry, and cancellation state;
- output-manifest hash and evidence locators;
- schema, provenance, safety, and task-specific evaluation results;
- human review requirement and final disposition.

Workers receive capability-scoped tools. No generic shell, browser, Drive, or
workbook access is granted unless the exact task policy explicitly allows it.

## Long-running agents

DataBossX does not keep agents alive by prompting them forever. Long-running work
is a sequence of bounded, resumable tasks.

Required controls:

- durable checkpoints and idempotency keys;
- expiring leases and monotonic fencing;
- heartbeats and cancellation;
- bounded retries, circuit breakers, and dead-letter review;
- token, time, cost, and external-write budgets;
- deterministic restart reconciliation;
- exactly-once logical outcomes, even when transport is at-least-once;
- operator-visible progress and the next blocking decision.

## Implementation sequence

### Phase 1: contract and evaluation

1. Add the machine-readable provider registry.
2. Add capability request and candidate outcome schemas.
3. Add a synthetic evaluation corpus for extraction, provenance, prompt
   injection, retries, and cancellation.
4. Add route-decision and cost records.
5. Add local inference adapters behind the same interface.

### Phase 2: Flowise pilot

1. Pin one Flowise release in an optional lab profile.
2. Build one synthetic title-extraction flow.
3. Export, hash, and evaluate the flow.
4. Confirm Flowise has no production credentials or direct writes.
5. Decide whether the visual layer saves enough operator time to retain.

### Phase 3: local model benchmark

1. Benchmark the current machine with LM Studio or Ollama.
2. Benchmark candidate local hardware only with the same fixtures and settings.
3. Publish a scorecard before any purchase decision.

### Phase 4: fine-tuning experiment

Begin only after reviewed correction data and baseline evaluations justify it.
A successful adapter is still disabled until independent review and explicit
catalog promotion.

## Acceptance criteria

This ADR is successful when:

- all providers use one capability contract;
- swapping a model or runtime does not change workflow authority;
- no lab tool can write canonical state or protected artifacts;
- every result is attributable to exact inputs, versions, and evidence;
- restart, timeout, duplicate delivery, stale lease, and cancellation are tested;
- quality and cost are measured before adoption;
- local-only policy makes remote egress technically impossible;
- the operator can see current work, blockers, cost, evidence, and safe next move
  from one DataBossX command center.

## References

- Flowise repository and releases: https://github.com/FlowiseAI/Flowise
- LLaMA-Factory repository: https://github.com/hiyouga/LlamaFactory
- AMD Ryzen AI Halo developer platform:
  https://www.amd.com/en/blogs/2026/amd-powers-next-generation-agent-computers-with-new-ryzen-ai-hal.html
- DataBossX OS blueprint: ../DATABOSSX_OS_BLUEPRINT.md
