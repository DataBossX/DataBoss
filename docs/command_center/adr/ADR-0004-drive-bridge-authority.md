# ADR-0004 — Drive bridge is built and proven, but performs no real writes

- Status: **Accepted**
- Date: 2026-08-01 · Cycle `DBX-CC-10000X-20260801-001`

## Context

The verified Drive state (read-only, `search_files`):

| Folder | ID |
| --- | --- |
| `DataBossCommandCenter` | `1n-FNvfJEeS9rX5a-A8IWkveBF5qU6_DT` |
| `00_COMMAND_INBOX` | `15nGmdJ56RnzazsF3uIn_g--eVzC7moaC` |
| `receipts` | `16Xrt-iCM71X9Y81JFCsTgvUbJ3VmLL7m` |

The directive's other folders (`01_ACTIVE_JOBS` … `99_ARCHIVE`) do not exist,
and `receipts` collides in intent with the proposed `03_RECEIPTS`.

The only authorization artifact is
`00_AUTHORIZATION_REQUEST__DBX-DATABOSSX-CONTROLLED-REPAIR-20260801-001__NOT_YET_ACTIVE`,
which the directive states is **not active** and confers no authority. The
directive further forbids creating or moving Drive folders until the exact
parent, contents, conflicts, and authority are verified.

## Decision

Build the full Drive protocol and prove it against an injectable client; perform
**zero** real Drive mutations.

1. `DriveClient` is a port. `InMemoryDriveClient` is the only implementation
   wired, and it supports fault injection (`corrupt_next_readback`,
   `truncate_next_upload`).
2. The publish protocol is: stage locally → hash staged bytes → upload an
   immutable version → **download it back from the store** → compare digests →
   only then advance the manifest pointer.
3. `plan_control_room()` computes the idempotent folder plan, reports the
   `receipts` vs `03_RECEIPTS` conflict, creates nothing, and returns
   `authority: "NOT_GRANTED"`.
4. Import validates hash and schema before a record exists. A file appearing in
   a folder never executes anything.
5. Reconciliation compares the manifest against the store, so a missed change
   notification is corrected rather than silently losing a version.

## Why read-back is non-negotiable

Desktop sync reporting "complete" is not a checksum. Both realistic corruption
modes are tested and both fail closed with the pointer unmoved:

- `test_readback_mismatch_refuses_and_does_not_advance_the_pointer`
- `test_incomplete_upload_is_detected_by_readback`

## Consequences

- The protocol is proven; only the client implementation is missing.
- The `receipts` vs `03_RECEIPTS` conflict is an **owner decision**. An agent
  renaming or duplicating an existing folder would be a mutation without
  authority.
- Open gaps C-3 and C-4 in `CURRENT_GAP_REPORT.md`.

## Activation checklist

1. Owner activates the authorization document.
2. Owner resolves the folder-naming conflict.
3. Implement `GoogleDriveClient` against the `DriveClient` port.
4. Re-run `DriveRedTeamTests` against the real client in a scratch folder.
5. Only then publish real receipts.
