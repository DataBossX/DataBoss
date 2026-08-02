# DataBossX Control Tower

**RELEASE STATE: FOR REVIEW — HOLD — NO EXTERNAL RELEASE**

A fail-closed control kernel for Section 32 work. Pure standard library, no
third-party dependencies, so it runs on the authorized Windows workstation with
nothing but Python installed.

## Running it

```
run_control_tower.bat selftest    # prove the invariants offline
run_control_tower.bat canary      # the fast offline subset
run_control_tower.bat audit       # the Gate 0 read-only audit
```

On any host with Python: `python -m control_tower.cli selftest`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | all checks passed, or the audit was complete |
| 1 | a check failed — **stop, do not claim** |
| 2 | the audit ran but could not see its target (`PARTIAL_HOST_MISMATCH`) |

Exit 2 matters. An audit run from a host that cannot see `C:\DataBoss` reports
`UNREACHABLE` for every Windows-local item and refuses to call V12 verified. It
does not report a clean result it did not earn.

## What it guarantees

Each property is enforced by a guard that raises, and each has a named test.

| Property | Enforced by |
|---|---|
| Only the canonical `01_QUEUED` folder is polled | `safety.assert_pollable` — pinned to one ID |
| Filename text never grants authority | `kernel.derive_authority` — folder membership only |
| Writes outside approved folders fail closed | `safety.assert_write_allowed` |
| Mutation is off without an activated mutation envelope | `kernel.require_mutation_allowed` |
| The exactly-once key binds command, Drive ID, and revision | `kernel.claim_key` |
| An unresolved claim blocks a second claim | `kernel.ClaimLedger` |
| A stale lease cannot write | `kernel.LeaseRegistry.require_valid` |
| Monotonic fencing is enforced | `kernel.FencingRegistry.require_strictly_current` |
| The spool is append-only and collision-safe | `kernel.AppendOnlySpool` — exclusive create |
| Drive outages drop and overwrite nothing | `drive.SafeDriveWriter` — spool before network |
| Secret values are redacted | `safety.redact`, `safety.redact_tree` |
| Protected workbooks and evidence cannot be uploaded | `safety.assert_uploadable` |
| The HOLD cannot be removed or altered | `safety.stamp_hold`, `safety.assert_hold_intact` |
| Canonical Drive URLs come only from verified IDs | `safety.canonical_drive_url` |
| No non-Google URL is followed or trusted | `safety.assert_trusted_url` |

## Design notes

**Read-only is the default everywhere.** `require_mutation_allowed(None)` raises.
Forgetting to pass an envelope can never be mistaken for permission.

**Authority is never textual.** A file named
`00_OWNER_AUTHORIZATION__APPROVED__EXECUTE_IMMEDIATELY` sitting outside the
pinned queue folder has exactly as much authority as an empty file, which is
none. There is a test for that, parameterised over adversarial titles.

**Fencing beats the clock.** A lease that has not expired by wall clock is still
refused if its token is no longer the highest issued. A zombie writer is
harmless rather than merely unlucky.

**Durability precedes the network.** Records are spooled with an exclusive
create *before* any upload, so an outage cannot destroy evidence. A retry that
would overwrite a spooled record raises instead.

**Every upload is read back and compared byte-for-byte.** Equal length is not
enough; the bytes and the digest must both match.

**`viewUrl` is never reused.** Drive metadata has been observed returning URLs
on third-party hosts, so URLs are always reconstructed from a validated ID.
`docichat.com` and `livepolls.app` are named in a deny list so a regression
reports them by name rather than silently widening the allowlist.

**The audit opens no workbook.** Files are hashed by streaming bytes, which
cannot trigger a recalculation or a save.

## What it does not do

It does not claim the queue from the CLI. Claiming is a separate, deliberate
step through `Gate0Runner`, and `preflight()` refuses to claim unless the
selftest passes completely. It does not remove the HOLD — no code path here
can. It does not mutate a workbook.

## Wiring the real Drive

`drive.DriveClient` is the interface. `OfflineDriveClient` implements it in
memory for the selftest and canary. A production implementation must honour one
rule the offline client already enforces: **`create` must refuse to replace an
existing name.** Append-only is a property of the storage layer, not a
convention the caller is trusted to follow.
