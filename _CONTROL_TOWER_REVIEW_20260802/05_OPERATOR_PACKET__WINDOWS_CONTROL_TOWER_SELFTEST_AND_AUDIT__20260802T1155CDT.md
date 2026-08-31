# SECTION 32 — OPERATOR PACKET

## Run the existing Control Tower on the Windows workstation (read-only)

**Release state: FOR REVIEW - HOLD NO EXTERNAL RELEASE**
**State: NON-EXECUTABLE DRAFT — staged in 07_HUMAN_APPROVAL. This is not a queue command.**

Prepared: 2026-08-02 11:55 CDT / 16:55 UTC
Prepared by: Claude Code independent reviewer lane (Linux container — cannot do this itself)
Authorized by: owner ruling `DBX-RULING-R01-GATE0-NONCONSUMING-20260802T1155CDT`

---

## What this does and does not do

This runs the **already-built** DataBossX Control Tower from draft PR #74 in **read-only**
mode on the one host that can actually see `C:\DataBoss`. It produces the first **complete**
Gate 0 audit — V12, workbook lock holders, Excel processes, Windows services, scheduled tasks.

It does **not** claim Gate 0. It does **not** open, save, recalculate, or touch any workbook.
It does **not** write to Google Drive. It does **not** merge or deploy anything. Claiming is a
separate deliberate step and is **not reachable from this CLI**.

Every check below was independently reproduced by the reviewer lane on Linux:
selftest **18/18**, canary **7/7**, code hashes **12/12 match**, dependencies **zero**.

---

## Before you start

1. **Do not open Excel.** Do not open any Section 32 workbook, PDF, or ZIP.
2. You need **Python** (3.8+) and **git**. Nothing else — the tower is standard-library only.
3. Leave the live Cursor worker **PID 49548** alone for now. Quiescing it is a separate step.

---

## Step 1 — get the code without disturbing `C:\DataBoss`

Open **Windows Terminal** or **PowerShell** as your normal authorized user.

> The working tree at `C:\DataBoss` is **not** modified by these commands. A separate
> worktree is created outside the repo so nothing in `C:\DataBoss\.worktrees\` — including
> the sealed V12 package — is touched.

```powershell
cd C:\DataBoss
git fetch origin claude/databossx-section32-recovery-ouyziy
git worktree add C:\DataBoss_ControlTower_20260802 FETCH_HEAD
cd C:\DataBoss_ControlTower_20260802
```

## Step 2 — prove the build before trusting it

```powershell
.\run_control_tower.bat selftest
```

**Expect: `control_tower_selftest: 18/18 passed, 0 failed`, exit code 0.**

If it is anything other than 18/18, **stop** and send the output. The audit refuses to run on
an unproven build anyway — it re-runs the selftest as a precondition and exits 1 if it fails.

## Step 3 — the complete Gate 0 audit

The audit needs to be told where the protected artifacts are. **Without these flags it will
report `UNREACHABLE` even on Windows**, so pass them exactly:

```powershell
.\run_control_tower.bat audit `
  --v12-path "C:\DataBoss\.worktrees\section32-v12-narrative-restoration-20260801\SECTION32_V12_NARRATIVE_RESTORATION__20260801T013849Z\package\HORIZON_SECTION32_V12_NARRATIVE_RESTORATION_INTERNAL_REVIEW_HOLD__20260801T021008Z.xlsx" `
  --repo-path "C:\DataBoss" `
  --workbook-dir "C:\DataBoss\.worktrees\section32-v12-narrative-restoration-20260801\SECTION32_V12_NARRATIVE_RESTORATION__20260801T013849Z\package"
```

### Reading the exit code

| Exit | Meaning | What to do |
|------|---------|------------|
| **0** | Audit complete, everything it needed was reachable | Send the report. This is the good outcome. |
| **2** | `PARTIAL_HOST_MISMATCH` — it could not see something | Send the report; the `unreachable` list says what. Usually a wrong path in Step 3. |
| **1** | Selftest failed — build not trustworthy | **Stop.** Do not claim. Send the output. |

The audit prints a `report:` path and a `sha256:`. On Windows the V12 line should read
`OBSERVED`, not `UNREACHABLE`, and the expected digest is:

```
D3937F46B3130A25719BB82CDAC702CECAA131BA5C5AACD4142BD346987D8D5D
```

**A `MISMATCH` on V12 is a hard stop.** Do not continue, do not claim, send it immediately.

---

## What to send back

Exactly one of:

- the `report:` file and its printed `sha256:`, plus the exit code; or
- the full console output if it failed; or
- a screenshot of the first error if it will not start.

### Do not send

- passwords, API keys, tokens, or secrets
- screenshots containing credentials
- workbook pages or client evidence
- a claim that it succeeded without the report file

---

## After the audit

**Stop and wait.** Do not claim Gate 0, do not open Excel, do not start a workbook writer.

Per owner ruling `DBX-RULING-R01-GATE0-NONCONSUMING-20260802T1155CDT`, the Gate 0 claim token
is live and the sole command is **not** retired — but claiming is still a separate deliberate
step, and these blockers remain open first:

1. the live unbound Section 32 Cursor worker **PID 49548**
2. the expired-but-still-active containment lease **`LEASE-DBX-V13-MULTI-WRITER-CONTAINMENT-20260801`**
3. the owner-activated bridge envelope **`TE-DBX-S32-BRIDGE-RESTORE-20260802T1043CDT`** (expires **2026-08-03 10:54 CDT**)

Section 32 completion stays locked until a true terminal receipt reads
`S32_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY`.

---

## Rollback

Nothing to roll back — every command above is read-only. To remove the worktree afterwards:

```powershell
cd C:\DataBoss
git worktree remove C:\DataBoss_ControlTower_20260802
```

`C:\DataBoss` and every workbook are untouched either way.

---

**FOR REVIEW - HOLD NO EXTERNAL RELEASE**
