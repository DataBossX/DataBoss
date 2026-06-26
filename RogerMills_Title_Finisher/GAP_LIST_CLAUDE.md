# GAP_LIST_CLAUDE.md — Open / Needs Verification

Roger Mills 31‑12N‑24W · Claude final pass · 2026‑06‑26.
Severity: **H**igh / **M**edium / **L**ow. Status: Open unless noted.
Every item below is a **true evidence gap** — it cannot be closed without a
source an automated cloud reviewer cannot reach (recorded instrument images,
OCC 1002A, OTC PUN production, recorded plat/survey).

## Structural / high-visibility gaps

| # | Sev | Item | Reason / what's needed |
|---|-----|------|------------------------|
| 1 | H | **All net acres = `TBD`** on Title sheet → every tract `REPORT TOTAL`/`TOTAL` = 0 | Fractions/quantum not in index. Need recorded deed images to compute net acres. Quantum cannot be tied out until then. |
| 2 | H | **HBP status conflict** on Alexander #1‑31 | Client describes well as **INACTIVE**; OCC RBDMS shows **ACTIVE (oil)**. Reconcile status and confirm OTC gross production before treating the section as held by production. |
| 3 | H | **Top-lease subordination** (all six 2026 Silver Oak leases) | Leases are paid-up **TOP leases @ 3/16**, springing only on termination of 2004-era prior leases. Prior-lease termination/HBP status unresolved → effective dates of the top leases are contingent. Preserved on Title/WI sheets; keep Open. |
| 4 | M | **NE/4 SW/4 unassigned** to any tract | Aliquot diagram flags "NOT in any subject tract per current legals — verify (may fall in lots)." 15/16 QQs covered. Confirm against recorded plat. |
| 5 | M | **Tract 5 acreage undetermined** (irregular gov't lots; W/2, Lots 1 & 4, SE/4 SW/4 part) | Section 31 is a township-boundary section; W & S tiers are government lots ≠ 40 ac. Confirm acreage from recorded plat/survey. |
| 6 | M | **Tract 6 / Tract 8 nominal acreage "VERIFY against plat"** | Lotted SW/SE tiers; nominal 80/120 ac may differ. Confirm from plat. |
| 7 | M | **Tract 4 duplicate document columns** | Book/Page `2251/0529` appears in cols **L & AE**; `2406/0228` in cols **M & AG**. Each balances independently (no acreage error) but they are redundant. Recommend merge after confirming they are the same instrument (deferred — see Changelog). |
| 8 | M | **"The Public" carries net‑positive interest** in 7 of 8 tract grids | Placeholder for affidavit / unknown-grantee rows. Verify these are not masking a true grantee before finalizing ownership. |

## Working-interest / leasehold chain gaps

| # | Sev | Item | Reason / what's needed |
|---|-----|------|------------------------|
| 9 | M | **Lalexander 1‑31 wellbore chain** (2385/0072; 2455/0446; 2698/0069) | ORRI vs WI correctly distinguished (Martin's Empire→Stride Bank is **2% ORRI, not WI**). Full assignment images/exhibits needed for chain continuity, assigned leases/depths, retained interests. |
| 10 | M | **Mortgage/lien burden chain** (2356/0001; 2356/0200; 2357/0001; 2357/0474) | Open until matched to recorded releases; full images needed for collateral/release scope. |
| 11 | M | **Historic leasehold HBP** (OGLs 1‑30: Chesapeake/EOG/Lortz/Devon/Jess Harris/TODCO) | Primary terms alone insufficient. Check production, pooling, shut-in, extensions, releases before concluding expired/HBP. |

## Document-level evidence gaps (from `raw` sheet, 239 flagged of 1,470)

These are recorded instruments reviewed only at index/snippet level. **A full
recorded image is required** to confirm interest, fraction, net acres,
reservations, depth limits, and burdens. Full detail in `SOURCE_MAP_CLAUDE.csv`
(Book/Page → doc type → parties → source file).

| Category | Count | What's pending |
|----------|------:|----------------|
| Confirm from recorded image (general) | 116 | interest / fraction / reservation / depth |
| Index row only — full image required | 37 | exact fractional interest & reservation language |
| Public snippet only — full image required | 36 | assigned leases, depths, burdens, Sec 31 coverage |
| Not found in reviewed materials (index-only) | 27 | terms, acreage, royalty, lease status |
| Assignment — leases/depths/burdens pending | 18 | chain continuity, assigned leases/depths, retained interests |
| Affidavit — heirship/probate facts pending | 5 | date-of-death, heirship, effective facts |

By document type (top): Lease 27, Assignment 25, O/L 20, ASGT 14, Mineral Deed 13,
MTG 12, Mortgage 10, Affidavit 8, Oil & Gas Lease 7, Affidavit of Heirship 6.

## Preserved title issues (verified present, not dropped)
Reservations/exceptions, depth clauses, NPRI (Runsheet C315 Non‑Participating
Royalty Deed), royalty reservations, term interests, trust ownership (Mitchell‑
Buonaccorsi, Daigle, Johnson, Tucker, Fuchs, etc.), probate/decedent gaps
("Deceased", Final Decrees, Affidavits of Heirship), lease/HBP issues, and
mortgage/release defects all remain in `raw`, `Runsheet`, the tract grids, and
Title notes. None were removed in this pass.
