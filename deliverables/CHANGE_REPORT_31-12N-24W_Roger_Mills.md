# Change Report — 31-12N-24W Roger Mills Cursory Title Report

**Deliverable:** `31-12N-24W_Roger_Mills_Cursory_Title_Report_(6-27-2026).xlsx`
**Tract:** Section 31, T12N, R24W, Roger Mills County, Oklahoma
**Date:** 2026-06-27 · 17 sheets (16 original + rebuilt `Summary`)

## Toolchain (added under `scripts/`)
- `recalc.py` — headless LibreOffice full-recalc + error/RECHECK scanner (JSON out).
- `build_title_report.py` — deterministic, non-fabricating audit/repair pass.
- `graft_media.py` — re-injects images/drawings openpyxl drops on save, fixes the
  `xmlns:r` binding, and sets `fullCalcOnLoad` so viewers recompute on open.
- `audit_columns.py` — adversarial column-balance + over-conveyance sweep.

Pipeline: `build_title_report.py` → `graft_media.py`. Validation recalcs run on a
throwaway copy (LibreOffice round-trip strips images, so it is never run on the
shipped file).

## Results (verified by `recalc.py`)
- **Errors: 154 → 0.** All 154 `#VALUE!` were on `WI 1!C10:C163`, caused by
  `=E*D$5` multiplying by `D5 = "TBD"` (text). Fixed by setting `WI 1!D5 =
  448.333333` — the value already carried in the workbook (`WI 1!C6`) and in
  `Template.xlsx`. Cell yellow-flagged `CONFIRM` with a Source comment.
- **RECHECK: 3 → 2.** `Tract 2!AE6` was a floating-point false positive (column
  subtotal `-4.5e-10`); made its integrity test precision-robust
  (`ROUND(AE7,9)`). The remaining two are **genuine** and intentionally left
  flagged (see below) — not silenced by fabrication.
- **Footing: 7 of 8 tracts PASS** (net acres = tract acres `D5`); WI 1 & WI 2 foot
  to their acreage cells. **Tract 8 FAILS by design** (curated current-ownership
  total 41.23 ≠ 40) and is yellow-flagged for examiner review.

### Footing model (important)
Tracts 2, 3, 5, 6, 7, 8 carry a curated **"CURRENT MINERAL OWNERSHIP"** block whose
hardcoded, sourced subtotal is the footing authority and explicitly *"supersedes
the incomplete chain above"*. The canonical pro-rata NET ACRES formula was applied
**only** where the chain grid is the sole net-acre source (Tract 1, Tract 4, WI 1,
WI 2) — applying it to curated tracts would double-count. The `Summary`
foots-check references each tract's true authority cell.

## Adversarial verification pass
A full **661-instrument-column** balance sweep + over-conveyance scan was run
(`audit_columns.py`) against a recalculated copy. Cross-checked against the
workbook's own live integrity flags, it confirms **exactly two genuine column
imbalances** — `Tract 2!AS6` and `CM6`. The other raw-sum "imbalances" are
intentional structures the workbook's `SUBTOTAL`-based check correctly ignores:
Tract 7 cols H/I are a mirrored sub-ledger (rows 161–194), and the WI sheets use
non-conserved working-interest participation columns. One real item the sweep
surfaced — WI 2 assignments granting WI to **unnamed** parties (col sums 5.0 /
4.875) — is now flagged (`WI 2!H6, I6`).

## Yellow flags written (22 cells, all from the prescribed taxonomy)
| Count | Note |
|---|---|
| 9 | OVER-CONVEYANCE: owner nets >1 — examiner review |
| 3 | HBP?: confirm lease still held by production |
| 3 | GAP: chain break — examiner review |
| 2 | CONFIRM: acreage vs legal description |
| 2 | NAME CONFLICT: recorded spelling variant |
| 1 | MISSING: NRI/WI calc pending |
| 1 | VERIFY: pull OCC pooling/spacing |
| 1 | VERIFY: pull OTC/GPT production status |

(The workbook also retains the prior abstractor's own highlighting; the 20 above
are the cells added/refreshed by this pass.)

## Open-items punch list (also on the `Summary` sheet)
1. **Williams family chain gap** — `Tract 2!CM5`, `D68–73`. Probate 1479/191
   distributes 8/7 of the estate interest; confirm "Gene Williams" = "Rogene E.
   Williams." EXAMINER REVIEW (RECHECK retained at `Tract 2!CM6`).
2. **Silver Oak / SilverOak** — `OGL!I3–8`, `Title!G12`. Recorded spelling
   variants (do not merge); NRI/WI for the 2026 O&L block pending.
3. **Alexander #1-31 HBP** — `Well 1!P3`, `WI 1!D2`, `Tract 7!K191`. Active per OCC
   but HBP UNCONFIRMED; pull OTC PUN production + OCC spacing.
4. **OCC / OTC regulatory pulls** — `Well 1` (E/O/P columns). Pull OCC
   pooling/spacing/1002A and OTC/GPT production status.
5. **Pro-rata over-conveyances** — `Tract 4!E56,E59,E99`; `WI 1!E11,E13,E15`;
   `WI 2!E10,E11`. Owners net >1.0. Pro-rata footing is an allocation, not a
   deed-by-deed derivation. EXAMINER REVIEW.
6. **Tract 2 chain break** — `Tract 2!AS5`. MD 933/226 grantor conveys UND
   3/791.47 with no grantee row; column does not balance (RECHECK retained at
   `Tract 2!AS6`).
7. **Truncated owner name** — `Tract 2!D71`. "on T. Williams, Jr." is truncated
   upstream and identically truncated in the Runsheet — **cannot be restored
   without inventing**; flagged, not guessed.
8. **WI acreage confirmation** — `WI 1!D5` set to 448.333333 from the workbook's
   own `C6` / `Template.xlsx`; CONFIRM against the legal description.
9. **WI 2 assignments to unnamed parties** — `WI 2!H6, I6`. Assignments 1608/0038
   & 1567/0006 grant working interest to blank-named rows (column sums 5.0 /
   4.875). EXAMINER REVIEW.
10. **Tract 8 current-ownership overage** — `Tract 8!C97`. Curated current-mineral-
    ownership total is 41.23 NMA against a 40-acre tract — reconcile.

## Blockers / honest limitations
- The County Clerk PDF index (`12N_24W_31_-_Index.pdf`) and the Google Drive /
  local-PC sources named in the master prompt were **not provided** to this
  session. No legal facts (owners, fractions, Bk/Pg, instrument #s, dates) were
  invented. Every item that needs an external pull is yellow-flagged with the
  source noted.
- The two retained RECHECK flags (`Tract 2!AS6`, `CM6`) are genuine chain
  defects. Per the no-fabrication rule, balancing them would require inventing a
  grantee / a probate share, so they are documented as examiner-review items
  rather than "fixed."
