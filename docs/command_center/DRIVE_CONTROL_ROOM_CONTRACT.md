# DRIVE CONTROL ROOM CONTRACT — DataBossX Command Center

Implementation: `services/control_api/command_center/drive_bridge.py`
Authority decision: `adr/ADR-0004-drive-bridge-authority.md`

## Authority status: NOT GRANTED

**No Drive folder was created or moved, and no Drive file was written this
cycle.** The only authorization artifact,
`00_AUTHORIZATION_REQUEST__DBX-DATABOSSX-CONTROLLED-REPAIR-20260801-001__NOT_YET_ACTIVE`,
is explicitly not active and confers no TaskEnvelope, lease, fencing token,
WriterACK, or mutation authority.

## Verified current state (read-only)

| Folder | Drive ID | Status |
| --- | --- | --- |
| `DataBossCommandCenter` | `1n-FNvfJEeS9rX5a-A8IWkveBF5qU6_DT` | verified parent |
| `00_COMMAND_INBOX` | `15nGmdJ56RnzazsF3uIn_g--eVzC7moaC` | exists |
| `receipts` | `16Xrt-iCM71X9Y81JFCsTgvUbJ3VmLL7m` | exists — **conflicts with `03_RECEIPTS`** |
| `.git`, `.handoff_test`, `.zip_verify` | — | pre-existing scratch |

## Proposed layout (planned, not created)

```
00_COMMAND_INBOX   01_ACTIVE_JOBS   02_DECISIONS   03_RECEIPTS
04_ACCEPTED_ARTIFACTS   05_HOLDS_AND_AUTHORITY   06_SYSTEM_SNAPSHOTS   99_ARCHIVE
```

`plan_control_room()` returns what would be created plus the naming conflict,
with `created: []` and `authority: "NOT_GRANTED"`. **The `receipts` vs
`03_RECEIPTS` conflict is an owner decision.** An agent renaming or duplicating
an existing folder would be an unauthorized mutation.

## Command import rules

1. Every human-readable command has a machine-readable JSON sidecar or embedded
   canonical JSON block.
2. Required fields: `command_id`, `idempotency_key`, `created_at`, `actor`,
   `schema_version`, `content_sha256`, `risk_class`, `status`.
3. **A file appearing in a folder never executes anything.** Import validates
   the hash, then the schema, then creates a canonical database record — and
   only that record is executable. Proven by
   `test_file_in_a_folder_is_not_executable_by_itself`.
4. A declared `risk_class` of `PROHIBITED` is rejected at import.
5. Hash mismatch raises `ReadbackMismatch`; missing fields raise
   `SchemaValidationError`.

## Publish protocol (six steps, none optional)

```
1. stage locally (write .tmp → fsync → os.replace)
2. hash the STAGED BYTES
3. upload an immutable new version
4. DOWNLOAD IT BACK from the store
5. compare digests
6. only then advance the manifest pointer
```

**Desktop sync reporting "complete" is not a checksum.** Step 4 is the
verification that matters. Both realistic corruption modes are tested and both
fail closed with the pointer unmoved:

| Failure | Test |
| --- | --- |
| Silent corruption on read-back | `test_readback_mismatch_refuses_and_does_not_advance_the_pointer` |
| Truncated upload | `test_incomplete_upload_is_detected_by_readback` |

A failed version is left in place for forensics rather than deleted.

## Recorded per artifact version

`drive_file_id`, `drive_version`, `drive_mime_type`, `byte_size`,
`drive_parent_id`, application SHA-256, `drive_readback_sha256`, and
`drive_readback_at`. `DriveIntegrityWatcher` fails if any published version's
read-back digest does not equal its upload digest — and reports `NOT_RUN`, not
`PASS`, when there are no publications.

## Change tracking

Notification channels drop events and expire, so notifications are never the
only mechanism. `reconcile(parent_id)` compares the manifest against what the
store actually holds and reports `untracked_file_ids` and `missing_from_store`.
Proven by `test_missed_notification_is_caught_by_reconciliation`.

## Immutability

Accepted artifacts are never overwritten in place. New facts create a new
version; the artifact state machine allows `ACCEPTED → SUPERSEDED` only.

## Content restrictions

Never placed in Drive command metadata or receipts: raw title evidence,
absolute paths, `canonical_folder` values, secrets, or client identity. Receipts
are readable by a human **and** machine-verifiable via `content_sha256`.

## Activation checklist

1. Owner activates the authorization document.
2. Owner resolves `receipts` vs `03_RECEIPTS`.
3. Implement `GoogleDriveClient` against the `DriveClient` port.
4. Re-run `DriveRedTeamTests` against the real client in a scratch folder.
5. Only then publish real receipts under the verified parent.
