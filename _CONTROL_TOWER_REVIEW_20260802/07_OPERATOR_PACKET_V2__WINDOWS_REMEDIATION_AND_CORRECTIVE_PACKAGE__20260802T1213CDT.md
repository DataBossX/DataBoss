# SECTION 32 — OPERATOR PACKET v2

## Windows-side remediation and the append-only corrective package

**Release state: FOR REVIEW - HOLD NO EXTERNAL RELEASE**
**State: NON-EXECUTABLE DRAFT — staged in 07_HUMAN_APPROVAL. This is not a queue command.**

Prepared: 2026-08-02 12:13 CDT / 17:13 UTC
Prepared by: Claude Code independent reviewer lane (Linux container — cannot do this itself)
Governing authority: `DBX-RULING-R01-GATE0-COMMAND-SPENT-20260802T1213CDT`

> **Supersedes packet v1** (`05_OPERATOR_PACKET__...__20260802T1155CDT.md`, Drive ID
> `1cP_yr7uabRy2gW-gCOcFsFbh_4D5I5qM`). v1 is preserved unmodified. **Steps 1–3 below are
> unchanged from v1 and remain correct.** Only v1's closing section was wrong: it described
> the Gate 0 claim token as live. Under the governing ruling **the command is spent.**

---

## The one thing that changed

**The Gate 0 command is SPENT.** `DBX-S32-CONTAINMENT-TERMINALIZE-AND-CLEAN-AUTHORITY-COMPILE-20260801T1846CDT`
must **not** be claimed, re-claimed, retried, or given a second terminal receipt. The 11:10 CDT
receipt is its sole terminal outcome.

The missing START/CLAIM receipt **remains a material control defect** of record. It does **not**
reopen the command, and it does **not** authorize reconstructing a backdated START/CLAIM.

A new clean-authority command — new command ID, new TaskEnvelope, new lease, next monotonic
fencing sequence — is required before any further Gate 0 work. That comes **last**, after
everything below passes.

---

## Before you start

1. **Do not open Excel.** Do not open any Section 32 workbook, PDF, or ZIP.
2. You need **Python** (3.8+) and **git**. Nothing else — the tower is standard-library only.
3. **Do not claim the queue.** Nothing in this packet claims anything.

---

## Step 1 — get the code without disturbing `C:\DataBoss`

> A separate worktree is created **outside** the repo, so the working tree and everything in
> `C:\DataBoss\.worktrees\` — including the sealed V12 package — are untouched.

```powershell
cd C:\DataBoss
git fetch origin claude/databossx-section32-recovery-ouyziy
git worktree add C:\DataBoss_ControlTower_20260802 FETCH_HEAD
cd C:\DataBoss_ControlTower_20260802
```

Governing term 6 requires independently reproducing the **current PR #74 head or an explicitly
pinned successor**. Record the commit you actually ran:

```powershell
git rev-parse HEAD
```

## Step 2 — prove the build before trusting it

```powershell
.\run_control_tower.bat selftest
```

**Expect `18/18 passed, 0 failed`, exit 0.** Anything else: stop and send the output. The audit
re-runs the selftest as a precondition and exits 1 if it fails.

## Step 3 — the complete Gate 0 audit (read-only)

**Without these flags the audit reports `UNREACHABLE` even on Windows.** Pass them exactly:

```powershell
.\run_control_tower.bat audit `
  --v12-path "C:\DataBoss\.worktrees\section32-v12-narrative-restoration-20260801\SECTION32_V12_NARRATIVE_RESTORATION__20260801T013849Z\package\HORIZON_SECTION32_V12_NARRATIVE_RESTORATION_INTERNAL_REVIEW_HOLD__20260801T021008Z.xlsx" `
  --repo-path "C:\DataBoss" `
  --workbook-dir "C:\DataBoss\.worktrees\section32-v12-narrative-restoration-20260801\SECTION32_V12_NARRATIVE_RESTORATION__20260801T013849Z\package"
```

| Exit | Meaning | Action |
|------|---------|--------|
| **0** | Audit complete | Send the report. Good outcome. |
| **2** | `PARTIAL_HOST_MISMATCH` | Send it; the `unreachable` list says what. Usually a wrong path above. |
| **1** | Selftest failed | **Stop.** Send the output. |

V12 should read `OBSERVED`, digest `D3937F46B3130A25719BB82CDAC702CECAA131BA5C5AACD4142BD346987D8D5D`.
**A `MISMATCH` on V12 is a hard stop.**

---

## Step 4 — remediation (governing term 6)

All four must pass before any new authority is staged:

1. **Execute and prove the bridge-restoration envelope** `TE-DBX-S32-BRIDGE-RESTORE-20260802T1043CDT`
   (draft Drive ID `159gQIvazu4RWDB8wmZSYuJxsEM9NC5gb`), stopping at its own terminal receipt.
   **Activation expires 2026-08-03 10:54 CDT.**
2. **Quiesce or positively bind PID 49548** — the live unbound Cursor Section 32 worker scoped to
   `C:\DataBoss\_TASKS\DBX-SEC32-MAX-DEFENSIBLE-UPDATE-20260727-A1`. Without touching a workbook.
3. **Append-only terminalize and release** the expired containment lease
   `LEASE-DBX-V13-MULTI-WRITER-CONTAINMENT-20260801` (expired 2026-08-02T02:48:41Z, writer PID
   42668 dead, fencing sequence MISSING) with coherent global-register updates.
4. **Verify no competing writer and no workbook lock.**

---

## Step 5 — the append-only corrective package (governing term 5)

Must **not** alter, replace, rename, delete, or overwrite the 11:10 receipt. Must state plainly
that it is a **superseding correction record, not another Gate 0 terminal receipt**.

| Required item | Finding | Who |
|---|---|---|
| `.sha256` sidecar for Drive ID `1qwdfvWUGJiWmzEc6Ll4_BdD2z3kvcGwE`, from **exact returned bytes** | R-04 | **Windows host only** |
| Explicit F-02 scope ruling, or `NOT APPLICABLE` with reason | R-02 | **Windows host only** |
| Quarantined V13 WIP path, hash, disposition | R-03 | **Windows host only** |
| Exact actor, machine, process, authority, lease, fencing, readback facts | — | Windows host (reviewer-lane facts already published) |
| Explicit "superseding correction, not a terminal receipt" statement | — | Already satisfied by `DBX_CORRECTION_02` and the governing ruling record |

Declared baselines to reconcile against, carried forward **unverified**:

- F-02 inventory SHA-256 `648104BF819B3AA4B5E6F753C2677402A076C7F25B7CDB94799FD250C68249AD`
  — 177 occurrences / 12 strings actual; 156 / 9 proposed; 21 / 3 already predicated.
  **The proposal is not mutation authority.**
- Quarantined V13 WIP SHA-256 `FF8D6CF349CCEE753FA62F5213F152C0F3B17D7B18A57E1BA7A1A63DB6CEBC58`

> Why the reviewer lane cannot produce the sidecar: its only channel would be transcribing ~20 KB
> of the receipt's bytes through a language model. That is not a trustworthy byte channel, and a
> single slip would manufacture a false mismatch against the most consequential record in the
> matter. It must come from the host that wrote it.

---

## Step 6 — only then, a new clean-authority command (governing term 7)

Proposed through the existing control plane. Must carry a **new command ID**, new TaskEnvelope,
new lease, **next monotonic fencing sequence**, exact V12 pointer and hash, explicit permitted
paths, rollback, tests, and the unchanged HOLD. **It must not silently reuse the spent command.**

---

## What to send back

- the `report:` path and printed `sha256:`, plus exit code, from Step 3
- the commit you ran (`git rev-parse HEAD`)
- the bridge-restoration terminal receipt title from Step 4
- or the exact BLOCKED/FAILED title and its stated reason

**Do not send** passwords, keys, tokens, credential screenshots, workbook pages, client evidence,
or a success claim without a Drive receipt.

---

## Not authorized by any of this

No workbook mutation, no report-completion activation, no PR merge, no deployment, no client-data
release, no HOLD removal, no external release. PR #74, #76, #77 and related integration PRs remain
**draft and unmerged**. Section 32 completion stays locked until a true terminal reads
`S32_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY` — which now requires the **new**
command, not the spent one.

## Rollback

Steps 1–3 are read-only; nothing to roll back. To remove the worktree:

```powershell
cd C:\DataBoss
git worktree remove C:\DataBoss_ControlTower_20260802
```

---

**FOR REVIEW - HOLD NO EXTERNAL RELEASE**
