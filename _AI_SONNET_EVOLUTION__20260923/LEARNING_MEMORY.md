# Learning memory: reviewed records vs. forbidden raw claims

This governs the LEARN stage of `evolution_loop.py` and any future port of
it into the canonical kernel. It exists because issue #68 requires:

> Reviewed learning memory; raw model claims never become durable knowledge.

and the blueprint's non-negotiable rule #2:

> No fabrication. Unknown, missing, unreadable, inapplicable, inferred,
> assumed, and externally researched are distinct values.

A `LearningRecord` is a durable claim about *what worked*. Getting this
wrong is exactly how a self-improvement loop teaches itself to trust its
own unverified output — the failure mode issue #68 exists to prevent.

## The two stores

| Store | File | Who can write to it | What it means when present |
| --- | --- | --- | --- |
| **Learning memory** | `learning_memory.jsonl` | only `learn()`, only when both `reviewed_by` and `review_note` are supplied by the caller | "A human read this receipt and confirmed the lesson in `lesson_summary`." |
| **Quarantine** | `learning_quarantine.jsonl` | `learn()`, by default | "A cycle finished with this terminal state. No human has confirmed anything about it yet." |

Both are append-only `.jsonl` (one `LearningRecord` per line, via
`_append_jsonl`). Neither is ever truncated or rewritten by this module.

## What MAY be stored in learning memory

A record may move from quarantine into memory only if **all** of the
following hold:

1. **The cycle produced a terminal receipt.** `learn()` takes a `Receipt`,
   never a bare proposal or intermediate stage output. No lesson is
   recorded from a cycle that did not finish.
2. **The terminal state is in `LEARNABLE_TERMINAL_STATES`**:
   `PROMOTED_DRAFT_PR_ELIGIBLE`, `REJECTED_ADVERSARIAL`,
   `REJECTED_BUILD_UNVERIFIABLE`, `VETOED`. These are the four states that
   carry a specific, attributable reason (a passed gate sequence, a named
   failing probe, a failing test, or a named veto) — not an ambiguous or
   crashed state like `AUDIT_CHAIN_COMPROMISED` or
   `AUTHORIZATION_DENIED_SCOPE`, which mean "something is wrong with the
   system," not "something is known about the improvement."
3. **A human supplied `reviewed_by` (a real identity string) and
   `review_note` (free text).** Both are required; `learn()`'s tests
   (`test_reviewed_by_without_note_is_still_quarantined`) confirm that
   supplying only one still quarantines the record.
4. **`lesson_summary` is exactly the human's `review_note` text — never
   anything this module generated.** `learn()` does not summarize, does not
   quote `proposal.evidence`, and does not paraphrase the receipt. If the
   human's note is wrong, that is a human-authored and human-attributable
   error, not a laundered model claim.
5. **The record is bound to `source_receipt_hash`.** A learning record with
   no traceable receipt is not a learning record — it is an opinion.

Concretely, acceptable content for `lesson_summary`:

- "Confirmed: modules matching `*_config.py` are routinely missed by the
  substring heuristic; the seed catalog should special-case them." (a human
  noticing a real gap in `find_untested_modules`)
- "Rejected as expected: the `client_evidence` category veto fired
  correctly when a test proposal was manually tagged with that category."
  (confirming a control works)
- "False positive: `uncovered.py` is a fixture generator, not
  production code; the veto for `min_reversibility` should not have fired
  here — investigate before reusing this heuristic broadly."  (a reviewed
  record can *record a bug*, which is exactly the kind of durable knowledge
  worth keeping — as long as a human, not the model, is the one asserting
  it)

## What is FORBIDDEN, unconditionally

1. **Any unreviewed record treated as knowledge.** By default (no
   `reviewed_by`/`review_note`), everything goes to quarantine. Nothing
   reads from quarantine as if it were established fact — quarantine is
   scratch space for a human to triage later, not a knowledge base a future
   cycle is allowed to query.
2. **The model's own evidence text, verbatim, as the lesson.**
   `proposal.evidence` (e.g. `{"target_module": "...",
   "source_module_count": N}`) is *input* to a cycle, never *output*
   knowledge. It is preserved inside the receipt (for traceability) but
   `learn()` never copies it into `lesson_summary`.
3. **Confidence, value, risk, or score fields treated as ground truth.**
   `ImprovementProposal.confidence` is the proposer's self-reported number.
   Storing "confidence: 0.7" in learning memory as if it were a measured
   fact would let the system's own untested self-assessment compound across
   cycles. A `LearningRecord` never carries these raw numeric fields — only
   `cycle_terminal_state` (an enum decided by deterministic code, not by the
   proposal) and `lesson_summary` (human text).
4. **Agreement as evidence.** Per the blueprint's model-routing section: "A
   second model may challenge a candidate, but agreement is not evidence."
   Nothing in this module runs two models and stores their agreement as a
   fact, and no future extension should — a second automated opinion is
   still zero human reviews.
5. **Secrets, credentials, or client evidence of any kind.** The ADVERSARIAL
   stage's `secret_scan` probe blocks promotion before a receipt is even
   written if a secret pattern is found in build output; `learn()` never
   runs on an unpromoted, non-terminal cycle, so this is defense in depth,
   not the only control. Independently: OBSERVE never reads file contents
   and BUILD never touches real repository bytes, so client evidence cannot
   reach this stage in the first place (see `README.md`, "What this is
   not").
6. **Silent edits to a stored record.** `_append_jsonl` only appends. If a
   reviewed record is later found to be wrong, the correction is a *new*
   record referencing the old one's hash — never an edit or deletion. This
   mirrors the blueprint's "append-only derivation" rule.
7. **Auto-promotion from quarantine to memory.** There is no code path,
   scheduled job, or CLI flag that moves a quarantined record into memory
   without a human re-invoking `learn()` with `reviewed_by`/`review_note`
   filled in. Quarantine records are not retried automatically.

## Why this split, specifically

A self-improving loop that lets its own unreviewed output become its future
input is the textbook failure mode the "Autonomy boundaries" section of
issue #68 is designed to prevent, and it is exactly what the blueprint's
rule #7 ("Conflicts remain conflicts... a qualified human resolves material
conflicts") and rule #12 ("Complete audit") already forbid for the title
pipeline. This module applies the same discipline to its own learning: a
`LearningRecord` is trustworthy in direct proportion to how traceable and
how human-reviewed it is, never in proportion to how confident the
generating cycle claimed to be.
