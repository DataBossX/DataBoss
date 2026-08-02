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
| H — Independent review | H | see review record |

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

**The successor was NOT queued and NOT executed.** It sits in `04_BLOCKED` awaiting a separate
express owner activation.
