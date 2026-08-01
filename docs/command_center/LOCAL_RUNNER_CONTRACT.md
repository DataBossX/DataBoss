# LOCAL RUNNER CONTRACT — DataBossX Command Center

Implementation: `services/control_api/command_center/runner.py`

## Direction of communication

The runner **never listens**. It claims work outbound, executes, and posts
results outbound. There is no inbound port, no reverse tunnel, and no LAN API,
so there is nothing to authenticate from outside. `serve()` refuses any non-
loopback bind (`test_public_binding_is_refused`).

## Mandatory verification order

Every one of these is a hard stop. Nothing runs until all pass:

1. Envelope exists.
2. Envelope has not expired.
3. Nonce unused (replay refused).
4. Lease is `ACTIVE`.
5. **Fencing sequence is current** — an older sequence fails closed.
6. Every declared input hash still matches what is registered.
7. Approval consumed, when `risk_class = APPROVAL_REQUIRED`.
8. Adapter is on the allowlist.
9. Execution mode is one the adapter supports.
10. Simulation-only mode refuses `REAL`.

The runner re-verifies from the database rather than trusting what it was
handed, because the runner is the thing being constrained.

## Approval consumption timing

The single-use approval is consumed **as late as possible** — after all
verification, immediately before the adapter runs. An abort during verification
therefore does not burn the owner's token.

## Path handling

The runner never accepts a caller-supplied absolute path. It maps
server-controlled logical relatives onto its own working root:

```
workroot/jobs/<task_id>/         one directory per job
workroot/jobs/<task_id>/out/     outputs, removed on rollback
```

`resolve_relative_path` rejects absolute paths (POSIX, Windows drive letters,
UNC), `..` traversal, and null bytes. Anything resolving outside the root is
refused.

## Adapter allowlist

There is no generic "run shell" or "run SQL" adapter, so arbitrary execution is
**not representable in a TaskEnvelope** — not merely blocked at the edge.

| Adapter | Risk | Modes | Role |
| --- | --- | --- | --- |
| `status.read_posture` | READ_ONLY | READ_ONLY | VIEWER |
| `project.read_summary` | READ_ONLY | READ_ONLY | VIEWER |
| `artifact.verify_hashes` | READ_ONLY | READ_ONLY | REVIEWER |
| `title.simulate_interest_rollup` | SIMULATION | SIMULATED | OPERATOR |
| `report.simulate_draft_build` | SIMULATION | SIMULATED | OPERATOR |
| `drive.publish_receipt` | APPROVAL_REQUIRED | SIMULATED, REAL | OWNER + step-up |
| `artifact.promote_candidate` | APPROVAL_REQUIRED | SIMULATED, REAL | OWNER + step-up |

## Atomic writes and rollback

Outputs are written to `path.tmp`, `fsync`ed, then `os.replace`d — atomic within
the directory. On any failure the job's `out/` tree is removed and the receipt
records `rollback_completed: PASS`.

## Failure behaviour

Any exception produces a receipt with `outcome: ABORTED_FAIL_CLOSED`, the reason
recorded verbatim, the job moved to `FAILED`, and prose beginning
`[SIMULATED] ... FAILED CLOSED ... Nothing was changed.` **Silent partial
success is treated as a defect** — proven by
`test_runner_disconnect_mid_job_leaves_a_failed_receipt_not_silence`.

## Restart and duplication safety

- Durable outbox table; delivery is separate from state change.
- `ux_attempt_task_completed` — at most one COMPLETED attempt per task.
- Nonce table refuses envelope replay.
- Idempotency keys collapse duplicate commands.

## Limits and kill switch

`DEFAULT_LIMITS`: 120s wall clock, 8 MiB output, network DENY, filesystem
WORKDIR_ONLY. A `kill_switch_path` file, when present, makes the runner refuse
all work with `KillSwitchEngaged` before any verification runs.

## Data boundary

The runner posts **metadata and receipts only**. Artifact bytes stay in its
working directory. Raw client evidence never crosses to the cloud control plane.
In this lane every artifact is synthetic and marked `synthetic: true`.

## Current status

`simulation_only=True`. `REAL` execution is refused. Enabling it requires a
separate authorization, a resolved Drive authority, and a re-run of the runner
red-team tests against the real adapters.
