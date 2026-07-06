# Roger Mills 2 — Deep Audit: 31-12N-24W Cursory Title Report (7-6-26) NHE

**Scope:** target report `31-12N-24W Roger Mills Co. Cursory Title Report (7-6-26) - NHE.xlsx`
audited against reference layout `Template.xlsx` (the QA'd Section 31 rebuild).
**Automation:** `automation/roger_mills_2_format_fix.py` applies every item below.
**Date:** 2026-07-06

---

## 1. Visual alignment map (target vs. Template)

The template's visual language: **Calibri 10 body text**, dark-navy `1D2330`
banner bands with bold white text, steel-blue `1F4E78` runsheet header, light-gray
`E2E3E5` column headers, soft-gold `FFF2CC` totals with `BF9000` edges, thin
`BFBFBF` data grids, and `D9E2F3`-ruled ledger cells on OGL.

| Sheet | Discrepancy found | Resolution |
|---|---|---|
| **OGL** | Target body was Arial 9/10 mixed with Calibri; borders/date formats inconsistent; 21 column-width and 70 row-height diffs | **Exact per-cell style transfer** from template (rows are record-aligned 69/69) — fonts, fills, borders, alignments, number formats (`m/d/yy` dates, `#,##0.00` acres, `0.0000` royalty), widths and heights |
| **Runsheet** | Header band `1D2330` vs template `1F4E78`; 437 row-height and 27 width diffs; alignment drift on ~14.8k cells | **Exact per-cell style transfer** (rows aligned 566/566). Exception: template column C carries a 129-char autofit artifact — target's readable 18.1 width kept |
| **Title** | Body Arial 9 vs Calibri 10; tract banners only spanned B:C; totals unstyled; net-acre cells showed raw 16-digit floats | Rule-based restyle: Calibri 10 throughout; navy banner across B:G on all 12 section bands; `E2E3E5` headers with grid borders; `FFF2CC`/`BF9000` totals; owner rows gridded, net acres `0.00000000`, royalty `0.0000`; portrait print like template |
| **Overview** | 4 width diffs (A, B, AH, AI), scaffolding row heights, landscape vs portrait | Template widths/heights adopted for rows 1–9 and 43–56 only; **map rows 10–42 untouched** (target's merged-cell plat grid and mediumGray spacing-unit shading differ structurally from the template's finer grid — adopting its heights would distort the map) |
| **WI 1 / WI 2** | Arial 9/10 body vs template Calibri 10; rows not structurally aligned with template | Font family aligned to Calibri 10; structure, widths and ledger logic kept (target's +1/−1 assignment tally is content, not formatting) |
| **Well 1** | No header band (plain Calibri 11) vs template navy band | Navy `1D2330` band with white bold Calibri 10 on rows 1–2, white rules, template column widths, `m/d/yy` date formats |
| **PLAT** | Visible but completely empty in target; hidden in template | Hidden |
| **Tract 1–10** | Target Tract 1 already matches template Tract 1 **cell-for-cell** (4 differing cells out of 39,104); other tract sheets follow the same format | No changes — already template-conformant |

---

## 2. Data audit — verified clean

- **Acreage control:** all 10 tract gross acreages sum to **637.42** = Overview figure. ✔
- **Ownership math:** every tract's owner net acres sum exactly to its gross
  (T1 80.00, T2 160.00, T3 40.00, T4 80.00, T5 38.28, T6 51.00, T7 40.00,
  T8 32.80, T9 75.34, T10 40.00). ✔
- **No formula errors** (`#REF!` etc.) anywhere; cross-sheet formulas
  (`Title!C124 → 'Tract 4'!D5`, `Title!C209 → SUM(OGL!P65:P70)`) intact. ✔
- **Overview LAST ENTRY 2704/142** matches the latest runsheet instrument
  (Order Allowing Final Account, Runsheet row 557). ✔
- Tiny fractional interests (e.g. 0.00004 NMA) are genuine chain remainders, retained. ✔

## 3. Data corrections applied (47 guarded edits)

| # | Location | Before → After | Basis |
|---|---|---|---|
| 1 | `Title!B37`, `Tract 2!D21` | `…William Cobal Bain, Jr.` → adds `)` | unclosed parenthesis |
| 2 | `Title!C128`, `Tract 5!D2`, `Tract 8!D2` | `W. 1820 chains` → `W. 18.20 chains` | dropped decimal; same sentence reads "ADA W 18.20 chains"; `Title!C158` carries the correct figure |
| 3 | `Title!C167`, `Tract 9!D2` | `SE/corner` → `SE corner`; `feet:` → `feet;`; `beginning.of 31…` → `beginning, of 31…` | metes-and-bounds punctuation |
| 4 | `OGL!J28` (OGL 27) | trailing stray token `aol` removed from legal | transcription artifact |
| 5 | `OGL!H67` (OGL 66) | `a/k/a Gena Williams, a/k/a Gena Mitchell Williams, Gena W. Moore` → `Gena W. Moore, a/k/a …` | scrambled name order (primary name last) |
| 6 | `OGL!H70` (OGL 69) | `Kevin Johnson Johnson, Trustee…` → `Kevin Warner Johnson, Trustee…` | duplicated word; trust name and Runsheet row 546 confirm |
| 7 | `Title!B62`, `Tract 2!D62`, `Runsheet!H173/AA173` | `Hazel Trust Hamilton` → `Hazel Hamilton Trust` | clerk-index surname-first entry ("Hamilton, Hazel Trust") was flipped mechanically; grantee of Mineral Deed 1123/100 |
| 8 | `Title!B68`, `Tract 2!D78` | `RIVE Lind McCaul Trust` → `Rive Lind McCaul Trust` | normalize record all-caps to report style |
| 9 | `Well 1!H3` | Spud `6/5/2006` → `Not confirmed of record` | stated spud **postdates** stated completion 5/19/2006; completion is corroborated by both workbooks, the spud date by nothing — flag for OCC Form 1002A verification |
| 10 | `OGL!N` column, 26 rows | stale draft **8-tract numbering** → final **10-tract layout** | see below |

### OGL "Tracts" column re-derivation (item 10)

The column still used a pre-final draft scheme (e.g. `All (1-8)` in a 10-tract
report; one cell had literally become the date `1/2/1900` from a typed `2`).
Each entry was re-derived from that lease's own legal description against the
final tract layout:

| OGL # | Old | New |
|---|---|---|
| 1–4 | All (1-8) | 1, 3, 4, 5, 7, 9, 10 |
| 8, 24, 40, 49, 50, 61, 67, 68, 69 | 1, 3, 4, 7, 8 | 3, 4, 7, 10 |
| 9 | 2, 3, 5, 6, 7 | 5, 6, 9 |
| 10 | 5, 6 | 5, 6, 8 |
| 12 | All (1-8) | 5, 6, 8 |
| 15 | *(date 1/2/1900)* | 2 |
| 20 | 2, 5 | 2 |
| 23 | 2, 3, 5, 6, 7 | 5, 9 |
| 25 | 2, 3, 5, 7 | 5, 9 |
| 46 | All (1-8) | 5, 8 |
| 48 | 5, 6, 7 | 5, 9 |
| 62 | 5 | 8 |
| 64 | 1, 3, 4, 5, 6, 7, 8 | 1, 3, 4, 5, 7, 9, 10 |
| 65 | All (1-8) | All (1-10) |
| 66 | All (1-8) | 1, 3, 4, 5, 6, 7, 8, 9, 10 |

West-strip key used: the 91-ac strip (W 18.20 chains of Lots 1 & 2 + N/2 Lot 3)
splits into the North 40 (of which the South 32.80 = **Tract 8**, remainder in
**Tract 5**) and the South 51 = **Tract 6**; `SE/4 SW/4` → T5; `S/2 Lot 3`,
`Lot 4`, `S/2 NE/4 SW/4` → T9; `NE/4 SE/4` → T10.

## 4. Flagged for verification (deliberately NOT changed)

- **`OGL!J65` (OGL 64)** reads `…NE/4 SW/4, S/2, Lots 3-4, …`. The comma after
  "S/2" is almost certainly transcription (sister leases 65/66 read "S/2 of
  Lot 3, Lot 4", and the 355.34-ac recital only reconciles without a full S/2).
  Tracts were assigned on the S/2-of-lots reading; confirm against Bk 2693/337.
- **Name variants carried as-of-record:** `Bary Ellen Sitzman` (Mineral Deed
  913/261) vs later `Mary Ellen Sitzmann`; `James F. Menehan` (Deed 517/136) vs
  OGL 40's `James E. Menehan`. Record names retained; consider a/k/a notes.
- **OGL 65/66 gross recitals (375.34 ac)** don't tie to the sum of tracts their
  legals cover — recital figures from the instruments, verify at the register.
- **Runsheet rows 565–566** are blank index shells (also blank in the source);
  retained.
