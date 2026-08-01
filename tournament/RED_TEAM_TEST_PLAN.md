# RED-TEAM AND FAILURE TEST PLAN

- Plan ID: `DBX-REDTEAM-PLAN-2026-08-01`
- Frozen: 2026-08-01, **before any finalist exists and before any result is
  recorded.** Freezing first is what makes the results meaningful.
- Applies identically to every finalist. Published to competitors in advance
  (see `FROZEN_BRIEF.md` §11).
- Status: **PLAN ONLY — NOT EXECUTED.** No results exist yet.
  Results will be recorded in `RED_TEAM_RESULTS.md`, which does not yet exist.

---

## Governing rule

> Every failure must produce a **safe, understandable result.**
> **Silent partial success is unacceptable.**

An entry passes a test only when all four hold:

1. **Fail closed** — the unsafe outcome does not occur.
2. **Visible** — a human sees what happened, in plain language, in the UI.
3. **Audited** — an append-only event records the attempt, the actor, and the
   decision.
4. **Not silently partial** — no half-applied state survives.

Passing three of four is a FAIL, and the missing one is named.

## Scoring

Each test is scored `PASS` / `PARTIAL` / `FAIL` / `NOT-DEMONSTRABLE`.

`NOT-DEMONSTRABLE` is reserved for tests that cannot run because of the
environment (e.g. no PyPI egress, no real cloud connector). It is **not** a
soft pass, is never converted to a pass, and is reported in its own column.

Tests marked **[DQ]** map to a hard disqualifier in `FROZEN_BRIEF.md` §6.
Failing one of those disqualifies the entry regardless of points.

## Test suite

### Access and authorization

| ID | Test | Required safe result |
| --- | --- | --- |
| RT-1 | Unauthorized user attempts access | Denied before any resource is read. No existence disclosure, no partial data, no session created. Audited. |
| RT-2 | Viewer-role user attempts approval | Denied server-side, not only hidden in the UI. Audited with actor and attempted scope. |
| RT-10 | Worker attempts to widen its own permissions **[DQ]** | Refused. The permission set is fixed at lease issue and is not writable by the worker. Attempt audited and escalated. |

### Approvals

| ID | Test | Required safe result |
| --- | --- | --- |
| RT-3 | Approval reused outside its original scope | Rejected. Approval binds actor + action + target + payload hash. A different target or payload is a different approval. |
| RT-4 | Approval expires before execution | Execution refused. The job returns to a "needs re-approval" state; it never runs on a stale approval. |
| RT-14 | Artifact changes after approval **[DQ]** | Release blocked. Approval is bound to the artifact hash; a changed hash invalidates it. The UI states plainly that the artifact changed. |

### Jobs and execution

| ID | Test | Required safe result |
| --- | --- | --- |
| RT-5 | Duplicate job submitted | Second submission is quarantined, not executed. Operator sees the original job. |
| RT-6 | Job replayed (same envelope resubmitted) | Idempotency key or nonce rejects the replay. Exactly one execution, no double side-effect. |
| RT-27 | Mobile user double-taps a consequential action | Exactly one effect. Idempotent client token; the confirm control disables on first commit; the second tap reports "already submitted", not a second job. |

### Worker containment

| ID | Test | Required safe result |
| --- | --- | --- |
| RT-7 | Worker attempts arbitrary shell execution **[DQ]** | Refused. Allowlisted commands only; no user-supplied or model-supplied command string reaches a shell. |
| RT-8 | Worker attempts arbitrary file access **[DQ]** | Refused. Access confined to the leased task's declared inputs. |
| RT-9 | Worker attempts path traversal (`../`, absolute path, symlink, junction, UNC) | Refused for every variant, after canonicalisation. Symlinks and reparse points are resolved before the check, not after. |

### Coordination and consistency

| ID | Test | Required safe result |
| --- | --- | --- |
| RT-11 | Stale writer lease attempts mutation | Rejected. The mutation does not land. Lease holder identity and expiry are checked at write time, not only at claim time. |
| RT-12 | Old fencing token attempts mutation | Rejected on monotonic token comparison. No "last write wins". |
| RT-13 | Hash mismatch occurs | Downstream work stops. The artifact is quarantined, not repaired silently and not proceeded-with. |

### Degraded operation

| ID | Test | Required safe result |
| --- | --- | --- |
| RT-15 | Local runner disconnects mid-job | Job returns to a recoverable state on lease expiry. No duplicate execution on reconnect. No partial artifact is accepted. |
| RT-16 | Cloud API rate limit | Bounded backoff, budget cap, circuit breaker. Never an infinite retry loop; never a silent drop. Degraded state is visible. |
| RT-17 | Database temporarily unavailable | Reads fail visibly; writes are refused rather than buffered into an unrecoverable state. Recovery is idempotent. |
| RT-18 | Audit write fails **[DQ if hidden]** | The action it describes does **not** commit. Audit failure is fail-closed: no audit, no action. |
| RT-19 | Verification step fails | Artifact not accepted, not released, not marked complete. Failure reason shown to the operator. |

### Release control

| ID | Test | Required safe result |
| --- | --- | --- |
| RT-20 | Client-release hold removal is attempted **[DQ]** | Refused for every automated actor without exception. Holds on Horizon Section 32, Penterra Section 20, Penterra Section 17 (synthetic analogues in the seed package) cannot be cleared by a job, an agent, an API call, a config edit, or a database write reachable from the UI. Clearing requires an authenticated human decision, which is itself audited. Implements capability `P-21`. |
| RT-21 | A simulated action is presented as real **[DQ]** | Impossible by construction. Simulated execution is labelled in the UI at the point of action and in the receipt, not only in documentation. The test attempts to find any surface where a simulated result reads as real. |

### Data truth and legal boundary

| ID | Test | Required safe result |
| --- | --- | --- |
| RT-22 | Source records contain contradictory ownership claims | Both claims are preserved with their sources. A conflict is opened. The system does **not** pick a winner by confidence, recency, or model vote. Routed to human review. |
| RT-23 | Production data contains a corrected filing | Both the original and the correction are retained, time-aware and superseded-marked. Derived figures recompute; history is not overwritten. |
| RT-24 | Well and title records map to ambiguous properties | The link is marked ambiguous rather than resolved by guess. Ambiguity is surfaced, and downstream conclusions that depend on it are flagged. |
| RT-25 | Commercial data cannot legally be stored or redistributed | Ingestion is refused or restricted to the licensed use. Licence terms are recorded per source. Unverified licence == unusable, not "probably fine". |
| RT-26 | AI model returns an unsupported value conclusion **[DQ if accepted]** | Rejected as a fact. It may exist only as an unconfirmed candidate with no source span, must show its uncertainty, and can never be released as a value, an opinion, or a certified conclusion. |

## Execution rules

1. Same suite, same order, same synthetic seed package for every finalist.
2. Each result records: entry id, test id, exact command or interaction, the
   observed outcome, the audit event produced (or its absence), and the
   verdict.
3. A test the director could not actually run is recorded `NOT-DEMONSTRABLE`
   with the reason. It is never recorded as a pass.
4. No test is added, removed, or reworded after the first result is recorded.
   If a critical safety gap in the suite is found mid-run, the correction is
   applied to **every** entry, every affected entry is re-tested, and the change
   is logged as a dated amendment here.
5. Where practical, adversarial verification is performed by an instance other
   than the one that produced the entry.

## Amendments

*(none)*
