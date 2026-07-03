# QA_LOG_CLAUDE.md — Roger Mills 31‑12N‑24W (Final Claude Review Pass)

- **Prospect:** 25‑004 — Section 31, T12N, R24W, Roger Mills County, Oklahoma (640 ac, 8 tracts)
- **Reviewer:** Claude (final pass, order 3) · **Date:** 2026‑06‑26
- **Source workbook:** `31-12N-24W_Roger_Mills_Final_Updated_Title_Report.xlsx` (Google Drive, owner ryangille02@aol.com)
- **Candidate output:** `outputs/03_CLAUDE_VERIFIED.xlsx`
- **Report type:** Cursory (per Overview); cursory report dated 6/16/2026, last entry 2704/142, examiner RG.

> **Environment substitution.** The task referenced local Windows paths
> (`D:\Desktop\DataBossX\RogerMills_Title_Finisher`, `D:\Desktop\Database`,
> `D:\Desktop\Horizon\Roger Mills`) and intermediate files `01_CURSOR_VERIFIED.xlsx`
> / `02_CODEX_VERIFIED.xlsx`. This pass ran in a cloud session where those paths
> are unreachable and the Cursor/Codex intermediate files were **not present in
> the container or on Drive**. With the user's approval, the review was performed
> as a **single evidence pass** against the real `Final_Updated` workbook on
> Drive. No three-way Cursor-vs-Codex diff was possible (inputs absent); this is
> stated rather than fabricated.

## Scope of accessible evidence
- ✅ Full workbook (20 sheets) decoded and inspected cell-by-cell.
- ✅ Internal cross-sheet consistency, formulas, chain-of-title grids.
- ❌ **No access to recorded instrument images** (county clerk / OKCountyRecords
  API / OCC 1002A / OTC PUN). Items requiring an image to resolve remain Open by
  necessity — see `GAP_LIST_CLAUDE.md`.

## Tabs (unchanged — 20, same order)
`Overview, Title , PLAT, OGLs, Runsheet, Tract 1..8, WI 1, WI 2, Wells, raw, WIsheet, Title_BACKUP, Runsheet_BACKUP`

## Automated checks run

| # | Check | Result |
|---|-------|--------|
| 1 | Workbook opens; 20 tabs present, names & order unchanged | **PASS** |
| 2 | Chain-of-title grids balance (every conveyance column nets 0; no `RECHECK`) | **PASS** — 0 unbalanced columns across all 8 tracts |
| 3 | Broken formula references (`#REF!`) workbook-wide | **PASS** — 0 |
| 4 | Stale/orphaned external links | **FIXED** — 2 removed (see Changelog) |
| 5 | Embedded media / comments / drawings preserved in candidate | **PASS** — 2 images, 11 comment sets, 15 drawings intact |
| 6 | Tie-out: Overview ↔ PLAT ↔ Title ↔ Tract sheets (8 tracts each) | **PASS** (structural) |
| 7 | Aliquot coverage (16 quarter-quarters of Sec 31) | **15/16 assigned**; NE/4 SW/4 unassigned (flagged) |
| 8 | Wells researched & cleaned | **PASS** — sole well sourced to OCC RBDMS + ShaleXP |
| 9 | Duplicate document columns within tract grids | **1 finding** — Tract 4 (see Gap List) |
| 10 | NPRI / reservation / depth / probate terms preserved | **PASS** (carried in raw/Runsheet/Title notes) |

### Detail — Check 2 (chain balance)
Each tract sheet is a chain-of-title matrix: rows = parties, columns = recorded
instruments carrying −1 (grantor) / +1 (grantee). A built-in `=IF(..=0,"","RECHECK")`
row flags any instrument whose entries don't net to zero. Computed independently
for all 8 tracts: **every instrument column nets to zero** → no data-entry
imbalance. Document counts: T1=30, T2=60, T3=29, T4=28, T5=43, T6=8, T7=25, T8=62.

### Detail — Check 6/7 (tie-out & coverage)
- Overview map labels Tracts 1–8. PLAT legend lists Tracts 1–8 with legals and
  nominal acreage. Title sheet carries Tract 1–8 mineral blocks plus two
  Working-Interest blocks. Tract sheets 1–8 each exist. **Structurally ties out.**
- Aliquot diagram (PLAT) assigns 15 of 16 quarter-quarters. **NE/4 SW/4 is
  explicitly "NOT ASSIGNED"** — workbook already flags "verify (may fall in
  lots)." Kept Open.
- **Quantum does not tie out numerically:** every tract's net-acre column is
  `TBD`, so `REPORT TOTAL`/`TOTAL` evaluate to 0. Expected for a cursory report
  (fractions pending deed images), but means no acreage reconciliation is
  possible yet. Logged as a high-visibility open item, not an error.

### Detail — Check 8 (wells)
Sole well of record: **Alexander #1‑31 (of record LALEXANDER 1‑31)**, API
35‑129‑22925, operator Martin's Resources LLC, surface C NW/4 SE/4. OCC RBDMS GIS
status **Active (oil)**, ShaleXP corroborates active w/ operator-level production
through Mar 2026. Well-level volumes **unconfirmed pending OTC PUN**. Researched &
cleaned — **PASS**, with the active/inactive HBP reconciliation carried as an open
item (see Gap List #4).

## Verdict
The workbook is **internally consistent and structurally sound** (balanced chains,
no broken references, clean tie-out of tracts across sheets). All remaining
high-severity items are **true evidence gaps** that cannot be closed without
recorded instrument images unavailable in this session — each is documented in
`GAP_LIST_CLAUDE.md` as Open / Needs Verification with a reason. QA loop therefore
terminates per the rule "no high-severity errors remain or every remaining issue
is documented as a true evidence gap."

---

## Addendum — 2026‑07‑03 · Export-consistency QA (`scripts/qa_exports.py`)

Added a committed, stdlib-only regression guard that re-derives the ownership
math from the CSV exports independently and asserts the invariants a title report
must never violate. Run with `python3 scripts/qa_exports.py` after any export
regeneration (`report/gen_exports.py`); non-zero exit on any failure so it can
gate CI.

| Check | Result |
|---|---|
| Every tract foots: identified NMA + open NMA == gross ac (10/10) | **PASS** |
| Every tract's decimal interests sum to 1.000000 (10/10) | **PASS** |
| Section gross == 637.42; identified 302.16 + open 335.26 == gross | **PASS** |
| `ownership_by_tract.csv` ↔ `section_net_acre_summary.csv` agree per-tract and on totals | **PASS** (all rows) |
| Pull list = 63 rows (35 conveyed-fraction, 23 source-in, 5 regulatory) | **PASS** |
| OGL register = 69 leases | **PASS** |

**Result: 60/60 checks green (exit 0).** This confirms the four "best-moves"
exports are internally consistent and cross-agree; it does **not** close any
evidence gap — the 335.26 open NMA remain Open pending the recorded images listed
in `open_items_pull_list.csv`, exactly as required by the review contract.
