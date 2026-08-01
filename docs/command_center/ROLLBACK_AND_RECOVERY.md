# ROLLBACK AND RECOVERY — DataBossX Command Center

## Principle

Every failure path leaves the system in a state a human can read and act on.
Nothing is repaired silently, and nothing is left half-applied.

## 1. Job-level rollback (automatic, demonstrated)

On any adapter exception the runner:

1. removes the job's `out/` tree,
2. records `outcome: ABORTED_FAIL_CLOSED` with the verbatim reason,
3. adds `rollback_completed: PASS` to the receipt checks,
4. moves the job to `FAILED`,
5. writes prose beginning `[SIMULATED] … FAILED CLOSED … Nothing was changed.`

Demonstrated by `test_runner_disconnect_mid_job_leaves_a_failed_receipt_not_silence`.

Outputs are written `.tmp` → `fsync` → `os.replace`, so a crash mid-write leaves
either the old file or the new one, never a partial.

## 2. Transaction rollback (automatic, demonstrated)

State change, audit event, and outbox row share one transaction. If any part
fails, all three roll back. Proven twice:

- `test_state_change_and_audit_share_a_transaction` — injected audit failure
  leaves no lease row, and the scope stays claimable.
- `test_interrupted_transaction_leaves_no_partial_state` — injected outbox
  failure leaves neither lease nor audit rows, and the chain stays valid.

## 3. Lease recovery

| Situation | Recovery | Manual? |
| --- | --- | --- |
| Writer finishes normally | `release_lease` → `RELEASED` | no |
| Writer crashes | Heartbeat lapses past the stale threshold → `EXPIRED`; scope claimable | no |
| Lease TTL expires | → `EXPIRED` on the next claim attempt | no |
| Writer wedged but alive | `release_lease(force=True)` — **OWNER only**, emits `LEASE_FORCE_RELEASED` | yes |

A recovered scope always issues a **new, higher** fencing sequence. The old
writer's sequence is now stale, so any late write it attempts fails closed. That
is what makes recovery safe rather than a race.

## 4. Approval recovery

Approvals are single-use and expiring. There is no "un-consume". If a job fails
after consuming its approval, the owner issues a **new** approval — deliberately,
so a retry is always a fresh human decision.

## 5. Artifact recovery

Artifacts are append-only versions. Rollback means **pointing at an earlier
version**, never editing or deleting a later one:

1. Identify the last good `version_number` for the `logical_id`.
2. Register the corrected content as a **new** version.
3. Advance the manifest pointer to it.

Accepted versions cannot be updated or deleted at all — enforced by triggers.

## 6. Drive recovery

A read-back mismatch aborts **before** the manifest pointer moves, so the
current version is always one that was verified. The bad upload is left in place
for forensics rather than deleted. `reconcile(parent_id)` then reports it as
`untracked_file_ids`.

## 7. Audit recovery

The audit ledger is append-only and hash-chained; it is never repaired. If
`verify_audit_chain()` returns false:

1. **Stop all writers** — force-release every active lease.
2. Find the first broken link (`audit_id` order).
3. Treat everything after it as suspect.
4. Preserve the database file as evidence; do not repair in place.
5. Escalate to the owner. This is an incident, not a cleanup task.

## 8. Full-system recovery

The control database is reconstructible in priority order:

1. **Holds** — re-seeded from code by `ensure_baseline_holds()`. They can never
   be lost by data loss.
2. **Policy version** — from code.
3. **Receipts** — from Drive custody once the bridge is authorized.
4. **Artifacts** — from content-addressed local storage plus Drive versions.
5. **Commands and jobs** — historical; not required to resume safe operation.

Leases and fencing counters are deliberately **not** restored from backup:
restoring a counter could reissue a sequence, which would break the fencing
guarantee. A fresh counter starting at 1 with no active leases is correct after
a restore, because no writer from the old world can hold a valid lease.

## 9. Kill switch

Creating the file at `RunnerConfig.kill_switch_path` makes the runner refuse all
work with `KillSwitchEngaged`, before any verification. Removing the file
restores normal operation. In-flight jobs complete or fail closed on their own.

## Recovery ordering after a serious incident

```
1. engage the kill switch
2. force-release all leases (OWNER)
3. verify the audit chain
4. verify artifact hashes
5. reconcile Drive
6. confirm all four holds are present and immutable
7. only then release the kill switch
```
