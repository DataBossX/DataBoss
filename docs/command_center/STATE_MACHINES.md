# STATE MACHINES — DataBossX Command Center

Declared once in `services/control_api/command_center/state_machines.py` and
enforced in two places: the service layer calls `assert_transition`, and the
database rejects the same impossible moves via triggers. Two layers, because a
bug in one must not be able to corrupt durable state.

## Command

```
DRAFT → TRANSCRIBED → INTERPRETED → CONFIRMED → CLASSIFIED → DISPATCHED
```

Exits available from most states: `CANCELLED`, `REJECTED`, `EXPIRED`,
`QUARANTINED`. `DRAFT` may only cancel or quarantine — a request that was never
transcribed cannot be "rejected on its merits".

Skipping is rejected: `DRAFT → DISPATCHED` raises `InvalidStateTransition`.

## Job

```
CREATED → QUEUED → PENDING_APPROVAL → APPROVED → RUNNER_CLAIMED
        → EXECUTING → VERIFYING → COMPLETED
```

Exits: `REJECTED`, `EXPIRED`, `FAILED`, `QUARANTINED`, `ROLLBACK_REQUIRED`,
`CANCELLED`. `QUEUED → EXECUTING` is rejected — nothing runs without passing
through approval or explicit approval-free classification.

`FAILED` is not terminal: it may move to `ROLLBACK_REQUIRED` or `QUARANTINED`.

## Approval

```
NONE → REQUESTED → CHALLENGE_ISSUED → SIGNED_BY_HUMAN
     → VALIDATED_BY_RUNNER → CONSUMED
```

Exits: `REVOKED`, `TIMED_OUT`, `REJECTED`, `EXPIRED`. `CONSUMED` is terminal —
that is what makes single-use enforceable. The transition to `CONSUMED` is a
compare-and-swap `UPDATE ... WHERE consumed_at IS NULL`, so a concurrent replay
loses the race and raises `ApprovalAlreadyConsumed`.

## Artifact

```
DISCOVERED → HASHED → REGISTERED → CANDIDATE → REVIEWED → ACCEPTED
```

Exits: `REJECTED`, `SUPERSEDED`, `QUARANTINED`, `HOLD`. `HOLD` can return to
`CANDIDATE` or `REVIEWED` only when a human clears it in a separate lane.

**`ACCEPTED` may only move to `SUPERSEDED`.** Accepted artifacts are never
overwritten in place; new facts always create a new version. Enforced by
`trg_artifact_version_accepted_immutable` and
`trg_artifact_version_accepted_no_delete`.

## Review

```
REQUESTED → CLAIMED_READ_ONLY → REVIEWED → PASS | REQUEST_CHANGES
```

A reviewer may not mutate the reviewed target. This is structural rather than
checked: watchers receive a `ReadOnlyView`, which accepts only `SELECT`/`PRAGMA`
and whose `claim_lease`, `approve`, `remove_hold`, and `write` methods raise
`WatcherPermissionDenied`.

`CLAIMED_READ_ONLY → PASS` is rejected — a verdict requires a completed review.

## Terminal states

Computed, not hand-listed, in `state_machines.TERMINAL`: any state with no
outgoing transitions. Verified by `test_terminal_states_have_no_exits`.

| Machine | Terminal |
| --- | --- |
| command | DISPATCHED, CANCELLED, REJECTED, EXPIRED, QUARANTINED |
| job | COMPLETED, REJECTED, EXPIRED, QUARANTINED, CANCELLED |
| approval | CONSUMED, REVOKED, TIMED_OUT, REJECTED, EXPIRED |
| artifact | REJECTED, SUPERSEDED, QUARANTINED |
| review | PASS, REQUEST_CHANGES, REJECTED |
