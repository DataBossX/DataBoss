# HUMAN ACTION REQUIRED — Unblock Section 32 Gate 0

FOR REVIEW - HOLD NO EXTERNAL RELEASE

Prepared 2026-08-02 by the Claude Code supervisory lane (read-only, non-claiming).
This document is a human operator guide. It is NOT a command, NOT a TaskEnvelope,
and confers NO authority. It does not live in 01_QUEUED and must never be moved there.

---

## Why everything is stopped

Gate 0 requires reading the LIVE LOCAL Control Tower records. Only the Windows
workstation that owns `C:\DataBoss` can do that. Every cloud lane so far has been
an ephemeral Linux container with no access to that host, so none of them could
legitimately claim the command.

The claim token is UNCONSUMED. Nothing has been burned. You are not recovering
from damage; you are supplying the one missing thing: the right machine.

---

## Preflight — confirm you are on the right machine

Run in PowerShell:

    Test-Path 'C:\DataBoss'
    hostname
    whoami

`Test-Path` must return `True`. If it returns `False`, you are on the wrong
machine — STOP. Do not continue on any other host.

---

## Step 1 — Is the watcher already running?

    Get-Service   | Where-Object { $_.Name -like '*DataBoss*' -or $_.DisplayName -like '*DataBoss*' }
    Get-ScheduledTask | Where-Object { $_.TaskName -like '*DataBoss*' }
    Get-CimInstance Win32_Process |
      Where-Object { $_.CommandLine -like '*DataBoss*' -or $_.CommandLine -like '*watcher*' } |
      Select-Object ProcessId, CreationDate, CommandLine

Record the full output. You need the PID, process start time, and full command
line — the claim binds to them.

- **Something is running** → go to Step 2.
- **Nothing is running** → go to Step 3.

Do NOT kill any process you do not recognise. Do NOT force-release a lease.

---

## Step 2 — A watcher is already running

Do not start a second one. A second watcher is a second control plane and is
prohibited.

Check whether it is healthy: look in Drive folder `09_WATCHER_OUTPUT`
(ID `1EX7ye_MrwACJaS9f9E2bcSo7w4TW3kVC`) for a heartbeat from THIS host that is
newer than the records listed at the end of this document.

- Fresh heartbeat from this host → the watcher is alive. Let it claim the command
  on its own. Do not intervene. Skip to Step 5 and just watch for the receipt.
- No fresh heartbeat, but a process exists → the watcher is hung or orphaned.
  Do NOT kill it. Record what you see and stop; this needs an owner decision,
  because force-releasing an unknown process is a prohibited action.

---

## Step 3 — No watcher exists: start the existing one

Use the existing documented entry point. Do NOT write new code, do NOT create a
new queue, database, watcher root, or control plane.

If the entry point runs without any code or configuration change, start it and
go to Step 4.

If it needs repair or configuration first, that is a repository/configuration
mutation and requires bound authority. A prepared, non-executable envelope is
already waiting for you:

- `04_BLOCKED` → `DRAFT_AWAITING_RYAN_ACTIVATION__TE_DBX_S32_BRIDGE_RESTORE__20260802T1043CDT.json`
- Drive ID `159gQIvazu4RWDB8wmZSYuJxsEM9NC5gb`

Activate it explicitly if you want the repair done, then follow its test list.
Two of its tests are already proven from the cloud lane and recorded inside it,
but you must still re-prove them from this host and process identity.

---

## Step 4 — Claim the command exactly once

Claim ONLY this command:

- Drive ID `1C0C8ERuCYm6Rqso0ahLXMifhXqlYjinOlFkN5k29NCE`
- Command ID `DBX-S32-CONTAINMENT-TERMINALIZE-AND-CLEAN-AUTHORITY-COMPILE-20260801T1846CDT`

**Before claiming, re-read it and confirm the content hash:**

- canonical `text/plain` export, 6261 bytes
- SHA-256 `92A5A128A4BF2D8FF5FE0768456B7AE3633662BE9A45DE9A954DEA08BEC1498F`

A mismatch means the command changed underneath us — STOP and emit a blocked
receipt. Do not claim a command you cannot hash-match.

Then: acquire one lease, take one monotonic fencing token, bind machine/user/
executable/PID/process-start-time/command-line, and append the START/CLAIM
receipt to `02_RECEIPTS` (`1G8qW5lQCSuT8nEvSTOzHFVdH-EN3r5yR`). Upload it, then
read it back and confirm the bytes and SHA-256 match exactly before proceeding.

---

## Step 5 — Gate 0, read-only

Answer the command's ten required actions against the live local records:
containment control, every TaskEnvelope, ACK, lease, fencing record, claim
ledger, heartbeat, process command line, branch, worktree, allowed write root.

### V12 verification — WITHOUT opening the workbook

    $p = 'C:\DataBoss\.worktrees\section32-v12-narrative-restoration-20260801\SECTION32_V12_NARRATIVE_RESTORATION__20260801T013849Z\package\HORIZON_SECTION32_V12_NARRATIVE_RESTORATION_INTERNAL_REVIEW_HOLD__20260801T021008Z.xlsx'
    Test-Path $p
    (Get-Item $p).Length
    (Get-FileHash -Algorithm SHA256 $p).Hash

Expected SHA-256:

    D3937F46B3130A25719BB82CDAC702CECAA131BA5C5AACD4142BD346987D8D5D

`Get-FileHash` reads bytes only. It does not open, recalculate, or save the
workbook. Never open V12 in Excel to "check" it — that mutates it.

**Lock check** — an Excel owner file means someone has it open:

    Get-ChildItem (Split-Path $p) -Filter '~$*' -Force

Must return nothing. Also confirm no Excel process holds a handle.

**Preserved baselines** — confirm these are unchanged wherever they live locally:

- V10 `79668279F0CF1A49CDF6F599F611C7BE058D40D43FA54372F6B559E60D9E7F4C`
- V11 `81AE7941DC62C748CBAA57A0FCEEB77F24828440F3A954173284ED3DB0DB0369`

If V12 is missing, changed, locked, hash-mismatched, or cannot be tied to a
released lease and an accepted ACK — STOP fail-closed. There is no silent
fallback to V9, V10, V11, V13, or any August 2 derivative.

---

## Step 6 — Exactly one terminal receipt

Append ONE receipt to `02_RECEIPTS` using EXACTLY ONE sentinel:

| Sentinel | Use when |
|---|---|
| `S32_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY` | Containment is terminal, pointer resolved from exact evidence, clean package compiled |
| `S32_REQUIRES_OWNER_CONTROLLING_POINTER_DECISION` | Evidence cannot deterministically resolve V12 vs V9 — produce the two-option decision packet |
| `S32_AUTHORITY_REISSUE_COMPILATION_BLOCKED` | Any stop condition fired |

Mark every inapplicable field `NOT APPLICABLE` with a reason. Do not silently
omit fields. Upload, then read back and verify bytes and SHA-256.

Only the first sentinel unlocks the completion draft
(`1yLvVqVGxmcFrYxXhWxRU-VUehg7cdvxut4fEZsGXPPg`), and only through one fresh
exact TaskEnvelope with Codex as sole writer and a separate read-only reviewer.

---

## Fail-closed — stop immediately on any of these

Command/hash mismatch · missing or invalid TaskEnvelope · missing, rejected,
expired, duplicate, or mismatched ACK · missing, expired, ambiguous, or competing
lease · stale or non-monotonic fencing · unknown process or writer · open
workbook lock or Excel owner file · V12 path/package/size/hash failure · altered
V10 or V11 · unavailable rollback · unauthorized path · duplicate claim or
duplicate terminal · failed canary or receipt readback · secret exposure ·
evidence mutation · inability to create append-only receipts · wrong template or
controlling source · any request to merge, deploy, release, or remove the HOLD.

In every case: preserve everything, emit a precise blocked receipt, and stop.
Never guess.

---

## Current verified state (2026-08-02, ~10:53 CDT)

- `01_QUEUED` — exactly 1 command. Claim token UNCONSUMED.
- `05_COMPLETED` — empty.
- Gate 0 — NOT claimed, NOT terminalized.
- Drive bridge — outbound round trip PROVEN byte-exact
  (1376 bytes, `AD0CF2CF…B19F`, identical pre-upload and readback).
- Local Windows bridge — ABSENT from every cloud lane; unknown on your host until Step 1.

### Records written by the supervisory lane

| Folder | Drive ID | Bytes |
|---|---|---|
| 09_WATCHER_OUTPUT (canary) | `1Gp9OvkinACzkAmOhqh5HVaJ-N5TB9anR` | 1376 |
| 02_RECEIPTS (receipt) | `1OkJdvqzFculZrjScrLGRHFk8uVQQ6BZV` | 17954 |
| 02_RECEIPTS (sidecar) | `1KVw31PDoR3TzptcxBxx1WHMcFA61xPST` | 3895 |
| 04_BLOCKED (envelope) | `159gQIvazu4RWDB8wmZSYuJxsEM9NC5gb` | 7330 |
| 09_WATCHER_OUTPUT (checkpoint) | `1WFxgdwADbxnivx1sdP0ic8ggAs6EVTmE` | 4604 |

### Drive-side artifact snapshot — metadata only

Content was deliberately NOT downloaded. Routing raw client workbook bytes
through a cloud AI lane is a prohibited operation, so no workbook hash could be
computed cloud-side. These must be hashed on your host.

| Artifact | Drive ID | Bytes | Modified (UTC) |
|---|---|---|---|
| V9 advisory `HORIZON_SECTION32_V9_CHALLENGER_RECONCILED__20260731.xlsx` | `1cNRTW0jjlNi1RBPmKmk0nb1cef50E64a` | 514825 | 2026-07-31T14:39:24Z |
| `SECTION32_DIVERSIFIED_TEMPLATE_FILLED_PRODUCTION_DRAFT_HOLD_2026-08-02` | `1C7S6Lr2HVQnBFTWDHTvPbJDcL5zOnur9` | 2061776 | 2026-08-02T13:33:26Z |

**Note worth your attention:** the second artifact currently sits in `04_BLOCKED`,
consistent with the existing receipt
`DBX_RECEIPT__CONCURRENT_SECTION32_DERIVATIVE_DETECTED_BLOCKED__20260802T0833CDT`.
It is a noncontrolling derivative. It must not be treated as the controlling
source and must not be promoted without an explicit owner decision.

---

FOR REVIEW - HOLD NO EXTERNAL RELEASE
