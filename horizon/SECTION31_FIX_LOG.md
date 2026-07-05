# Section 31-12N-24W — what the finalizer fixed (2026-07-05)

Input : `00_FINAL TURN-IN WORKBOOK - 31-12N-24W HBP UPDATE 2026-07-05` (= the current
        best report; the `BEST_OF_BEST` copy is byte-identical in content).
Output: `SECTION31_12N_24W_ROGER_MILLS_FINAL_CLEAN_2026-07-05.xlsx`
Tool  : `horizon/section31_finalize.py` (deterministic, re-runnable, no fabrication).

## Corrections applied

| # | Complaint | Fix | Count |
|---|---|---|---|
| 1 | "assignment bk/pg where OGL numbers should be" | Title WI blocks: assignment Book/Page moved out of the OGL column → base OGLs `1–30`; the assignment instrument stays in the Comment | 13 cells |
| 2 | Expiration column polluted with a global disclaimer | Replaced the `HBP per OGL sheet / client direction…` boilerplate with the real status (`HBP`, top-lease exp date, `Open`, `OPEN / VERIFY`); disclaimer carried once in the Note block | 41 cells |
| 3 | "put the OGL number next to each owner that leased and carry it down like Tract 1" | Carried each leased final owner's OGL number into the tract OGL column, keyed to the OGL sheet lessor (e.g. Brawner→37, Browning→19, Deutsch→42) | 38 owners |
| 4 | "chain the WI like Tract 1 and put ASSN as the conveyance" | WI 1 conveyance row relabelled `ASSN` / `ASSN (wellbore)` | 18 cells |
| 5 | "no strange highlights except yellow for cells I need to look at" | Stripped the ad-hoc rainbow fills from the owner blocks; one color only — yellow — on genuine review cells (open balances, undetermined owners, unlocated vesting, curative) | 37 Title rows + tract rows |
| 6 | "keep tract totals equal to the acres" | 9 of 10 tracts already tie exactly. Tract 2 over-conveys of record (221.70 NMA vs 160.00 ac); carried every owner at record fraction, disclosed the 61.70 NMA delta, flagged the total yellow — **not** silently reduced (that needs the deed images) | 1 flag |

## What was deliberately NOT changed (and why)

* **The chain-out fractions / net acres** — they are the examiner's prior work, already tie
  to each tract's acreage (sum = 637.42 ac), and were derived from the runsheet without the
  deed images. Re-deriving them here would risk inventing title facts, which the project's
  "no fabrication" rule forbids. No net-acre or royalty formula was touched.
* **The wide conveyance matrix coloring (cols G+)** on the tract tabs — left as working-paper
  visualization. Only the human-facing owner summary (cols A–F) was cleaned. Say the word to
  strip the whole grid to yellow-only.
* **Overview map, OGL, PLAT, Runsheet, Well, Curative, rawdata tabs** — carried through intact.

## Still open for the examiner (yellow cells)

* Tract 2 — 61.70 NMA over-conveyance (Bain/Fuchs mineral chain); curative.
* Tracts 4, 5, 6, 7, 9 — "Balance of tract (owners undetermined of record)" plug rows.
* WI 1/WI 2 — assignee addresses "not located"; WI/NRI not determined of record (exhibits
  not examined per cursory scope).
* Anna T. Gibson — base OGL `56 or 57` not resolved.

Open in Excel and press **Ctrl+Alt+F9** to recalc before distribution.
