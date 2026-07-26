# SECTION 32 RECONCILIATION REPORT — Horizon, Beckham County, OK, T11N-R25W

**Timestamp:** 2026-07-26 17:08 CDT · **Task:** `DBX-CLAUDE-CODE-CLOUD-SEAT-20260726T1650CDT-001`
**Verdict: HOLD STANDS. The hold is correct and must not be released.**
**New finding this cycle: the PENDING copy shows no evidence of repair (D-14).**

---

## Artifact inventory — three copies, all identical in length

| Title | Drive ID | Bytes | Modified | Folder |
| --- | --- | --- | --- | --- |
| `Section_32-11N-25W_Beckham_County_Cursory_Title_Report 7-23-2026.xlsx` | `1CuhEg1bzvcgX0rtpcRu6DmNYfjiq6um_` | **2,991,406** | 2026-07-23 | `17Q1pflYos6ZcTcneJ_aX8XKyoREJGKsF` |
| `INTERNAL_REVIEW_COPY__HORIZON_BECKHAM_SEC32__20260726.xlsx` | `11eSRgFonY5l_6SwAbmPDIsbGeaLXyudO` | **2,991,406** | 2026-07-26 | `1PcqTa1tNI349pMbY1F8yu6JNzfHCq9KI` |
| `PENDING__HORIZON_BECKHAM_SEC32__INTERNAL_REVIEW__20260726.xlsx` | `112CZEOJtSUoY_O_BkVM4cVIchCbimkpk` | **2,991,406** | 2026-07-26 | **PENDING FINAL VERIFICATION** `1-aYkvVWjwsApPBADZlxQedhwW-HnL774` |

### D-14 — the PENDING artifact is almost certainly the unrepaired 7/23 workbook

Byte length is identical to the byte across all three, spanning a claimed reconciliation cycle.
An OOXML package that had undergone *any* content edit — even a single cell — would almost
certainly change compressed length. Identical size across three copies is the signature of
**pure file copies with no repair applied.**

**This is the correct outcome under a hold** — no agent mutated a held workbook, which is exactly
right. The problem is **placement, not integrity**: an unrepaired file is sitting in a folder named
PENDING FINAL VERIFICATION, where a reader or an automated promotion step could reasonably mistake
it for remediated output.

**Required action (low risk, no content change):**
1. Hash all three on the Windows seat. If equal, the copy relationship is proven.
2. Annotate or rename the PENDING copy to state `UNREPAIRED_HOLD_COPY` so it cannot be read as
   verification-ready. **Do not delete anything** — all three are evidence.

## Carried-forward reconciliation holds (from control documents, not re-verified here)

State: `SECTION_HOLD_PREWRITE_READINESS_REFRESHED`. No writer lease. Open:

| Hold | Quantity |
| --- | --- |
| Canonical instruments vs source-ledger rows unexplained | **144 → 140**, difference **4** unexplained |
| Index pages | 62 |
| Missing binary hashes | 139 |
| Missing-source rows | 90 |
| Broken local references | 25 |
| Wrong targets | 140 |
| `1783/118` face and examiner treatment | unresolved |
| Missing index/creating faces; lineage; examiner-dependent conclusions | unresolved |

## Required classification of every difference — schema not yet populated

Each of the 4 unexplained instruments (and each of the 90 missing-source rows) must be classified
as exactly one of: valid duplicate · split/multi-part instrument · missing workbook row · missing
source-ledger row · superseded item · bad identifier normalization · unreadable source ·
unresolved substantive conflict · non-substantive formatting difference.

**Populated by this seat: 0 of 4.** The classification requires the source ledger and the workbook
side by side; neither is auditable at package level from a `drive_only` seat (2.99 MB exceeds this
seat's byte-exact transport limit — see `CLAUDE_CODE_BRIDGE_VERIFICATION.md` §Limit).

## Package-preserving edit method — pre-approved, not yet invoked

The repository already contains the correct mechanism; **no new tooling should be built.**
`horizon.controlled_loop` (`horizon/CONTROLLED_LOOP.md`) enforces exactly what Section 32 needs:

- project manifest is the authority for required checks and candidate hashes;
- a work order cannot weaken the gate;
- candidate/template/profile are SHA-256 verified before use;
- verified inputs are copied into a unique run directory; only snapshots are touched;
- one allowlisted defect repaired per iteration;
- formula restoration edits one worksheet XML part and **verifies every other OOXML package part
  byte-for-byte** before replacing the staged file;
- automatic rollback when a passing check regresses or the score does not improve;
- technical verification produces only a promotion package — it never writes to a canonical
  destination;
- human approval must name the exact staged output hash.

Its documentation already anticipates this exact hold: *"the current Section 32 manifest will
remain blocked until its source manifest, evidence crosswalk, and print-rendering receipts are
available. That is intentional: absence of evidence is not a pass."* **Concur — no override.**

Checks lacking a deterministic validator return `not_evaluated` and block verification. Because
`openpyxl` is not a calculation engine, any formula without a cached result is blocking and must be
recalculated through the approved desktop/LibreOffice workflow first.

## Completion figures

| Measure | Value |
| --- | --- |
| Artifacts located and cross-compared | **100%** (3 of 3) |
| Copy-relationship evidence gathered | length-identity only; hashes pending |
| 144→140 discrepancy classified | **0 of 4** |
| 90 missing-source rows resolved | **0%** |
| Workbook rows audited | **0%** |
| Release readiness | **0% — HOLD, correctly** |

## Required next actions

1. Hash the three copies on the Windows seat; prove or disprove the copy relationship (D-14).
2. Annotate the PENDING copy as an unrepaired hold copy.
3. Freeze controlling lineage, counting rule, source/hold matrix, corrected target mapping,
   backup, rollback, and package allowlist **before any lease** — as already directed.
4. Issue the `horizon.controlled_loop` work order only after step 3, with real manifest hashes.
   **Do not invent missing authority hashes.**

**The Section 32 hold must not be removed until reconciliation is complete, every material
discrepancy is resolved or expressly documented, and the workbook passes independent validation.**

`client_released=false` · `canonical_promotion_authorized=false` · `leases_claimed_or_consumed=NONE`
