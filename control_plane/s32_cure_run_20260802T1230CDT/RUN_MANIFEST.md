# S32 Bounded Cure Run — DBX-S32-CURE-RUN-20260802T1230CDT

**Release state:** FOR REVIEW — HOLD NO EXTERNAL RELEASE

Control-plane evidence for the bounded cures authorized by
`04_OWNER_RULING__RETIRE_ORIGINAL_S32_GATE0_COMMAND_AND_REQUIRE_SUCCESSOR__20260802T1210CDT`
(Drive ID `1lgcSJItqzXZ-FbHt1Tm65Jly9WEv-imD33_QSzINXBM`,
text/plain export 3623 bytes, SHA-256 `8098B2428378150AAC1915B51D87E1D1CB1CC9279C6A7319CCDE80AE36FEB909`).

This directory contains **control-plane evidence only**: zero executable code, zero client
artifact bytes, zero workbook bytes, zero secrets.

## Executing lane

| Field | Value |
|---|---|
| Host class | `LINUX_EPHEMERAL_CLOUD_CONTAINER` |
| Authorized Windows Control Tower | **no** |
| Windows control kernel reachable | no |
| Lease / ACK / fencing source reachable | no |
| Branch | `claude/s32-gate0-successor-3njjie` |

## Invariants held for the whole run

- Excel never opened.
- Zero workbook or client-evidence files opened, copied, recalculated, repaired, renamed or mutated.
- Retired Gate 0 command never claimed, retried, moved as executable work, or given another terminal.
- Bridge-restoration envelope's single terminal slot **deliberately preserved**, not consumed.
- No command added to or removed from `01_QUEUED`.
- No second control plane, queue, lease store, ACK store or fencing source created.
- No Drive record edited, overwritten, moved or deleted — every write is additive.
- HOLD preserved on every record.

## Cure dispositions

| Cure | Ruling | Result |
|---|---|---|
| A — Windows bridge restoration | C | `NOT_DISCHARGED_HOST_BOUND` |
| B — Cursor PID 49548 | A | `NOT_DISCHARGED_HOST_BOUND` |
| C — Containment lease | B | `PARTIALLY_DISCHARGED` — ledger instrument published, canonical release host-bound |
| D — 1110CDT SHA-256 sidecar | D | **`DISCHARGED`** |
| E — F-02 scope | E | **`DISCHARGED`** as explicitly NOT RULED with reason |
| F — Quarantined V13 WIP | F | **`DISCHARGED`** as inaccessibility proof |
| G — Successor envelope | G | **`DISCHARGED`** as draft; ACK/lease/fencing specified but deliberately unissued |
| H — Independent review | H | **`DISCHARGED`** — `QUALIFIED_PASS`, 2 material + 7 defect + 4 minor findings |

Note the run-local cure letters are **rotated** relative to the owner ruling: ruling A is the
Cursor worker, ruling B the lease, ruling C the bridge. The mapping is published in full in the
correction record.

## Independent review outcome

An independent reviewer lane (separate context, instructed adversarially, did not author the
draft) returned **`QUALIFIED_PASS`** with two material defects. Both were real and both are cured
by append-only correction — the published draft was not edited, renamed or moved.

- **F-01 (material) — the fencing floor rule was unsound.** The constant floor `20260802174000`
  (≈2.03e13) does not dominate wall-clock counters routine on the executor's own platform
  (Windows FILETIME ≈1.34e17, .NET Ticks ≈6.4e17, epoch µs ≈1.78e15), the rule required no
  write-back, and two issuers below the floor would deterministically collide on the same token —
  the exact tie fencing exists to break. **Replaced** with kernel-side atomic compare-and-set with
  confirmed durable write-back; the constant floor is withdrawn and has no authority.
- **F-02 (material) — the filename overstated readiness.** The file is titled
  `DRAFT_AWAITING_OWNER_ACTIVATION` while its own body says `DRAFT_AWAITING_CURES_AND_OWNER_ACTIVATION`
  and seven prerequisites are unmet. **Superseded** — the title must be read as
  `DRAFT_AWAITING_CURES__`.

Also cured: `01_QUEUED` removed from the write allowlist (F-05); all eight prior-draft elements
restored to the P8 activation gate (F-07); prerequisite status restricted to MET/NOT MET with new
stop conditions keyed to R-02 and R-03 (F-03); P4 requalified as NOT MET pending Windows-host
confirmation of the sidecar (F-04); the superseded `T1210CDT` successor identity expressly retired
(F-06); cure-letter mapping published (F-08); provenance question surfaced for owner decision (F-09).

Referred to the owner unruled: Doc-export hashes pinned without revision IDs (F-11), and the
completion-gate sentinel string mismatch (F-13).

## Verified digests

| Artifact | Bytes | SHA-256 |
|---|---|---|
| 1110CDT Gate 0 BLOCKED terminal (`1qwdfvWUGJiWmzEc6Ll4_BdD2z3kvcGwE`) | 19946 | `52A969007216A3CE32305B030B520376734250B01CBB282C96451343A72C9708` |
| This sidecar (`1LDsdx_boxHcCo1l7dbAI95DG4xmoey1S`) | 3166 | `CDD99B7F03B84976D8E5E9ED23AF27808B3D7F958BE2A91D5DAAA047272BC291` |
| Owner ruling, text/plain export | 3623 | `8098B2428378150AAC1915B51D87E1D1CB1CC9279C6A7319CCDE80AE36FEB909` |
| Retired command, text/plain export | 6261 | `92A5A128A4BF2D8FF5FE0768456B7AE3633662BE9A45DE9A954DEA08BEC1498F` |

The sidecar was verified by full base64 readback and a byte-for-byte `cmp` against the
submitted bytes: **identical**, 3166 == 3166.

## Finding C-A-01 — pinned command hash still valid

The retired Gate 0 command Drive record was modified at `2026-08-02T17:13:15.723Z`, after the
owner ruling landed and after every prior record pinned its hash. Independent re-export and
re-hash shows the text/plain export is **still exactly 6261 bytes with SHA-256
`92A5A128…1498F`** — the modification changed no exported bytes.

Consequence: the bridge envelope's fail-closed input-hash pin remains valid, so the authorized
Windows executor will not trip a hash-mismatch stop condition on this account.

## Still open — owner / Windows Control Tower action required

1. Restore the Windows outbound-only bridge (activation expires **2026-08-03 10:54 CDT**).
2. Quiesce or conclusively disarm Cursor PID 49548 without workbook access.
3. Apply the lease terminalization instrument to the canonical lease store.
4. Rule the F-02 scope, or verify the inventory against `648104BF…49AD` and propose one.
5. Confirm the quarantined V13 WIP against `FF8D6CF3…BC58` read-only, in place.
6. Freshly verify V10 / V11 / V12 (V12 expected `D3937F46…8D5D`).
7. Remove the retired command from executable consideration — it is still the sole child of `01_QUEUED`.
8. Issue the successor's WriterACK, expiring lease and monotonic fencing token.

9. Ratify (or decline) the **provenance** of these cure records — they were prepared by a lane that
   is not the authorized Windows Control Tower the ruling names. See review finding F-09.
10. Rule the completion-gate sentinel string (F-13) and decide the Doc-revision pinning question (F-11).

## Verification disclosure

Two artifacts received full base64 readback and byte-for-byte comparison: the 1110CDT terminal
(input) and the sidecar (output, `cmp` identical, 3166 == 3166). **Every other record in this run
was verified by Drive-reported stored byte count only** — per-record SHA-256 was not computed by
this lane. That is a narrower verification than the STARTED receipt anticipated, and it is recorded
explicitly in the run terminal rather than left implied. Anyone can compute those digests from the
Drive IDs.

**The successor was NOT queued and NOT executed.** It sits in `04_BLOCKED` awaiting a separate
express owner activation, and after the correction it remains **not activatable** — ten of eleven
prerequisites are NOT MET under the corrected two-value vocabulary.
