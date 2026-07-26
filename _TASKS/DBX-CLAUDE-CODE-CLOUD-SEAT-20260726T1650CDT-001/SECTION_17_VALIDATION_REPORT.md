# SECTION 17 VALIDATION REPORT — Penterra, Campbell County, WY, T47N-R75W

**Timestamp:** 2026-07-26 17:08 CDT · **Task:** `DBX-CLAUDE-CODE-CLOUD-SEAT-20260726T1650CDT-001`
**Verdict: REJECT_DO_NOT_PROMOTE.** Additionally: **do not execute the active A10 lease.**

**Artifact under test:** `PENDING__PENTERRA_CAMPBELL_SEC17__INTERNAL_REVIEW__20260726.xlsx`
Drive ID `1W_FwItz7xmFogVEwzUYk8jFI7iujdH0j` · 25,561 bytes · created/modified 2026-07-26T20:27:51Z
Location: **PENDING FINAL VERIFICATION** folder `1-aYkvVWjwsApPBADZlxQedhwW-HnL774`

---

## Pass 1 — Structural validation

| Check | Result |
| --- | --- |
| Format is a real `.xlsx` (OOXML), not CSV/PDF/ZIP export | **PASS** — `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| Sheets present | **PASS** — 2: `Index`, `QA Review` |
| Header schema on `Index` | **PASS** — `Document Type, Grantor, Grantee, Doc No, Book-Page, Date of Doc, Rec Date, Legal Description, Comments` |
| Metadata block rows 1–7 | present (`County`, `Lands`, `Date`, `Starting Date`, `Date Posted Thru`, `Indexed By`, `Project`) |
| Dates render as short dates (`M/D/YYYY`) | **PASS** on inspection |
| Package integrity / repair-free reopen in native Excel | **NOT EVALUATED — blocking.** Requires Windows + Excel; this seat is Linux-only |
| Formulas remain formulas · defined names · hyperlinks · print settings | **NOT EVALUATED — blocking.** Requires byte-level package access (see §Limitations) |

Per the controlled-loop safety contract, checks without a deterministic validator return
`not_evaluated` and **block** technical verification. Absence of evidence is not a pass.

## Pass 2 — Inventory reconciliation

| Metric | Value | Source |
| --- | --- | --- |
| Populated instrument rows | **197** | workbook `QA Review` sheet |
| Expected instrument count | **198** | workbook `QA Review` sheet |
| Unresolved difference | **1** | workbook `QA Review` sheet, status `OPEN` |
| Wholly unpopulated rows counted as populated | **1** (Book-Page `3163-0546`, all other fields `NOT DETERMINED`) | this audit — **D-13** |

**FAIL.** The packet cannot be represented as a fully reconciled 198-instrument abstract.

## Pass 3 — Evidence validation (workbook facts vs instrument faces)

Only **2 of 197** rows have direct primary-source face evidence available (E1 verification,
16:46 CDT). **Evidence binding coverage ≈ 1%.**

### Row `0331-0490` — **PASS**
E1 (2/2 pages, PDF SHA-256 `1809F809061DD65C101EF37B8FBFFA100AE6E5495D0DE0E6AEF18BF5A8ED1790`):
Warranty Deed · Opal E. Marquiss, a widow → Donald W. & Doris Wagensen · 10/22/1975 ·
Section 17 legal `W/2 and W/2 E/2` · **no separate document number on the face.**

Workbook: Doc No **blank**; legal `"W/2 and W/2 E/2 of 17-47N-75W, aol"`; comment records the
source-supported correction. **Fully compliant with E1.** (Control documents still list this as
open — see D-03.)

### Row `0285-0528` — **FAIL (BLOCKER, D-04)**
E1 (4/4 pages, PDF SHA-256 `F7E4D6F1385F8E6FEEDEAC6FA7B6D4E37FD9EF702CA2BD94EE167D63EDB148F6`):
Doc 379670 · Warranty Deed · → The Carter Oil Company · dated 12/3/1973, recorded 1/28/1974 ·
legal `All of Section 17` · **grantors expressly excepted and reserved all oil, gas, coal and
other minerals**, with entry and surface-use rights subject to surface-damage compensation.

E1 required treatment: legal description may remain `All of Section 17`, **but the row must carry
a material mineral-reservation and surface-only effect warning and must not imply the minerals
passed to Carter Oil Company.**

Workbook: legal `"All of 17-47N-75W, aol"` — acceptable. **`Comments` field is EMPTY.** The
required warning is absent.

**Effect on title:** the row as written asserts an unqualified Warranty Deed of all of Section 17
to Carter Oil Company. A reader constructing the mineral chain from this workbook would wrongly
conclude the minerals passed. This is a substantive misstatement of legal effect, and it is in a
file staged in PENDING FINAL VERIFICATION.

## Pass 4 — Contradiction detection (mechanical)

Applied a monotonicity test: `Doc No` should increase with `Rec Date` (document numbers are
assigned at recording). The index is otherwise strictly monotonic. Six violations:

| Ref | Book-Page | Doc No | Rec Date | Assessment |
| --- | --- | --- | --- | --- |
| D-05 | 0307-0002 | 368354 | 11/8/1974 | **probable 6↔8 transposition of 388354** (neighbour `0307-0004` = 388355, same day, same grantor) |
| D-06 | 1513-0025 | 639458 | 11/20/1998 | 639xxx belongs to ~1990 |
| D-07 | 1791-0124 | 862500 | 8/15/2002 | out of range vs 800456 / 805215 |
| D-08 | 3123-0423 | 1089993 | 1/19/2018 | expected ~1040xxx |
| D-09 | 2139-0282 | 867651 | 5/23/2006 | lower doc# **and** lower book-page but later rec date than 867754 |
| D-10 | 1551-0214 | 743314 | 7/9/1999 | lower doc# recorded after 748590 (6/24/1999) |

None may be corrected without the instrument face. **Recorded, not repaired.**

**Accepted, not a defect:** row `2202-0122` retains verbatim a range-direction conflict
(*"face also prints T47N-R75E, Sec. 17: NW/4 … range-direction conflict retained verbatim"*).
Retaining the source anomaly verbatim with a note is correct practice.

## Pass 5 — Independent review

This report **is** the independent pass. It was produced without relying on the producing agents'
conclusions, from a seat with no access to their working state. It confirms one prior finding
(row 35 requirement — already satisfied), refutes one (`Index!A10` value, D-01), reclassifies one
(stale copy → different artifact, D-02), and **originates seven** (D-04 through D-10, D-13).

## Pass 6 — Disagreement resolution

See `CROSS_AGENT_DISAGREEMENT_REPORT.md`. Six disagreements; the two that gate the active lease
(D-01 cell address, D-02 artifact identity) are **unresolved and blocking by design** — neither
may be settled by agent consensus, only by re-reading the artifacts side by side on a seat that
can open both.

## Pass 7 — Read-back and hash verification

**NOT COMPLETED. Blocking.** Three competing SHA-256 identities are in circulation for "the"
Section 17 workbook (D-11): `B19A6B97…`, `80A8D365…`, `B53B0876…`. This seat could not
independently compute a fourth: large binary payloads cannot be transported byte-exactly through
this seat's context (see `CLAUDE_CODE_BRIDGE_VERIFICATION.md` §Limit). Hash arbitration must be
done on the Windows seat.

---

## Limitations of this validation — stated exactly

1. **No native Excel.** Repair-free open/save/reopen unverified.
2. **No byte-level package access.** Formulas-remain-formulas, defined names, hyperlink targets,
   data validation, embedded objects, print settings, hidden content: **all unverified.**
3. **No hash computed by this seat** for any workbook (D-11 unresolved here).
4. **~99% of rows have no primary-source binding.** Passes 3 and 4 are complete only for the
   2 E1-covered rows; everything else is structural/mechanical inference.
5. **Priority sources unreachable:** `05ML-0463`, `030M-0595`, `030M-0615`, `033M-0425` are not in
   Drive (D-15). Attempted: title searches on `030M`, `033M`, `05ML`, `0463`.

## Completion status

| Dimension | Figure |
| --- | --- |
| Rows populated | 197 / 198 (99.5%) |
| Rows evidence-bound to a source face | 2 / 197 (**≈1%**) |
| Evidence-bound rows passing | 1 / 2 (50%) |
| Structural checks passed | 5 of 7 (2 blocked, not failed) |
| **Release readiness** | **0% — REJECT_DO_NOT_PROMOTE** |

## Required next actions, in order

1. **Freeze** `LEASE-S17-CURSOR-A10-20260726T1510CDT-001` (D-01, D-02).
2. **Repair `0285-0528`** — add mineral-reservation / surface-only warning (D-04). Highest value.
3. Publish the S17 artifact lineage graph reconciling the three hashes (D-11).
4. Identify the 198th instrument from the authoritative manifest without guessing (D-12).
5. Pull the six sequence-anomaly faces (D-05..D-10) and adjudicate.
6. Recover `030M-0595`, `030M-0615`, `05ML-0463`, `033M-0425` on the Windows seat or re-pull.

**client_released=false · canonical_promotion_authorized=false**
