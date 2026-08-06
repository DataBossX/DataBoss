# SECTION 32 V10 — CLAUDE CURRENT-DATA RESEARCH: STATUS REPORT

**Project:** Section 32, T11N, R25W, Beckham County, Oklahoma
**Client / asset:** Diversified Production LLC — OK48147.001.1
**Effective date:** August 5, 2026 · **Acreage:** 640.00 acres, more or less
**Status:** FOR REVIEW — HOLD, NO EXTERNAL RELEASE
**Report generated:** 2026-08-06 (UTC)

## WHY THE COMPLETION MARKER WAS NOT CREATED

`CLAUDE_V10_RESEARCH_COMPLETE.marker` has **deliberately not been written**.

All twelve registers are complete and every tract, Title owner row and lease is
included in them. But the mission was a **current-data revalidation**, and the
current-data half of that mission could not be performed from this environment.
Writing a completion marker would assert a currency that does not exist.

Outbound HTTPS is denied by this environment's network policy for **every host**,
verified 2026-08-06:

| Target | Result |
|---|---|
| `https://example.com` (control) | CONNECT tunnel failed, 403 |
| `okcountyrecords.com/search/beckham` | HTTP 403 |
| `oklahoma.gov/occ/divisions/oil-and-gas.html` | HTTP 403 |
| `gisdata-occokc.opendata.arcgis.com` | HTTP 403 |
| `deeds.com/recorder/oklahoma/beckham/` | HTTP 403 |

Evidence tiers **1, 2, 3, 4, 6 and 7 were unavailable**. No Beckham County Clerk
index or image, no OCC order or RBDMS record, no OTC production series, no
Secretary of State record and no SEC or company filing was retrieved. The Dropbox
authoritative source root `/11N 25W 32` is also unreachable — no connector.

Google Drive **was** reachable and supplied the V7 workbook, its receipt, the
project source tree and the governance manifests. That is what this packet is
built on, and every fact carries its own capture date.

The project's own `verified_gap_list.md` (committed 2026-07-11) independently
records the same constraint: *"Tier 1 county-record copies are not yet acquired
into the evidence manifest… retrieval must run from an authorized local machine"*
and *"Local Windows source path has not been independently inspected by this
cloud execution."*

## THE TWO CUTOFFS THAT DEFINE THIS REPORT'S REAL CURRENCY

Both are stated inside the workbook — on **hidden sheets only**.

1. **Recorded search-forward stops 03/02/2023** (Book 2400/551). The hidden
   PRESENT VESTING CONTROL sheet: *"Search-forward period: recorded corpus and
   county index through Book 2400/551 (03/02/2023) plus the 2026-08-05 Drive/OCR
   index sweep."* That is a **3.4-year gap** to the effective date.
2. **Production evidence stops 2022-08** — the OTC reporting cutoff, common to
   every well. That is a **47-month gap**. Every HBP conclusion in the report
   rests on it.

Neither cutoff appears on any visible sheet. A reader of the delivered report
cannot tell how current it is.

## THE CENTRAL DEFECT: THE WORKBOOK CONTRADICTS ITSELF

The hidden TITLE CHAIN QA sheet reports **Confirmed present record owner**:

| Tract | Confirmed present record owner | Visible Title rows shown as present owners |
|---|---|---|
| R1 NE/4 | 0.000000 | 12 |
| R2 N/2 NW/4 | 0.000000 | 20 |
| R3 S/2 NW/4 | 0.000000 | 7 |
| R4 N/2 SW/4 | 0.062500 | 20 |
| R5 S/2 SW/4 | 0.000000 | 3 |
| R6 E/2 SE/4 | 0.062500 | 22 |
| R7 W/2 SE/4 | 0.000000 | 3 |

The same sheet states plainly: **"No tract is documentarily closed"** and
**"Proof basis and owner status are independent. Status totals are not added to
proof basis."**

The visible Title sheet displays **87 named present mineral owners** across all
seven tracts. Essentially none of them is a confirmed present record owner by the
workbook's own register.

## UNRESOLVED ITEMS

| ID | Item |
|---|---|
| UNRESOLVED-01 | Neither declared control hash located. V7 lineage control (`c04f49bd…`, 726,715 B) and visual donor (`5166b700…`, 548,120 B) exist nowhere reachable. The Drive V7 receipt declares a *different* artifact: `a0bff0eb…`, 551,877 B. Lineage is unreconciled. |
| UNRESOLVED-02 | **2434/751** — Assignment FROM Diversified Production LLC and DP Legacy Central LLC TO **Teocalli Exploration LLC**, recorded after the search cutoff, held as an index lead only. If Section 32 is within it, Diversified is **not** the current claimant and Title, WI 1 and WI 2 are all wrong. Single highest-risk open item. |
| UNRESOLVED-03 | Three further post-cutoff Diversified-family filings unread: 2451/4, 2476/121, 2480/824. |
| UNRESOLVED-04 | 10 unresolved residuals displayed as **named** parties with ASSUMED notes — the V7 receipt states this conversion was deliberate. Largest is 65.000000 NMA to "Adolf Bollenbach, or his unlocated successors and assigns" on a 1910 deed. |
| UNRESOLVED-05 | 76 Title rows are 1949–1995 vestings displayed as present owners with no forward search past 03/02/2023 and no probate or death search. |
| UNRESOLVED-06 | HBP unevidenced at the effective date for **all 8 leases** (2022-08 cutoff). |
| UNRESOLVED-07 | 5 of 8 leases have **no recorded face held** (OGL 4, 5, 6, 7, 8) yet are displayed as HBP-supported or retained-active. |
| UNRESOLVED-08 | **Tract 5**: three wells producing a combined 3.68 Bcf under **no identified lease** (63/34 excluded as terminated of record) while all three Tract 5 Title rows show "None active". |
| UNRESOLVED-09 | **OGL 3** (332/74-75, face-reviewed, 3/16): its Viersen lessors appear in **no** Tract 1 owner row. Coverage gap. |
| UNRESOLVED-10 | **267/638** index-only competing out-conveyance (Euramerica 1973-A → First Western Oil & Gas Inc., undivided ½ of the NE/4) would defeat the Great Western 10 NMA row and OGL 8 entirely. Disclosed on a hidden sheet only. |
| UNRESOLVED-11 | 166 of 208 Runsheet entries carry "Section 32 — exact legal not extracted" instead of a complete legal description. |
| UNRESOLVED-12 | 40 Title Address values are bare historic recitals (1947–1995 deeds and leases) displayed as if current. |
| UNRESOLVED-13 | Diversified Production LLC's address (1600 Corporate Drive, Birmingham, AL 35242) could not be verified against any current official source. |
| UNRESOLVED-14 | Exhibits A, B, C and the Excluded Assets schedules for 2340/490, 2371/470 and 2389/500 are **not held**. No exact WI or NRI is calculable. |
| UNRESOLVED-15 | Crook #1-32 RBDMS status conflict (AC vs DRY) preserved unresolved. |
| UNRESOLVED-16 | LeGrand #2-32 location conflict: RBDMS quarter-call places it in Tract 3, lease lands in Tract 5. |
| UNRESOLVED-17 | No lease sweep (releases, surrenders, extensions, ratifications, top leases, new leases) for 03/2023–08/05/2026 on any tract. |
| UNRESOLVED-18 | Twin #1-32: 198 producing months cannot fit 2004-01 → 2022-08 alongside the stated 2004-09-30 first production. |
| UNRESOLVED-19 | 1 Runsheet Book/Page duplication requiring disambiguation. |
| UNRESOLVED-20 | Held county index PDFs (~101 MB and ~100 MB) and the Tax Roll folder were not paged — the best held route to the missing legals and to current addresses. |

## WHAT WOULD CLOSE THIS OUT

Run from an authorized Windows workstation with county and OCC access:

1. Read **2434/751** first. It can invalidate the report's central premise.
2. Pull current OCC/OTC production and well status through 08/05/2026.
3. Run the Beckham County forward sweep 03/2023 → 08/05/2026 for every owner,
   predecessor, lessee and assignee.
4. Retrieve the five unheld OGL faces (341/538, 340/323, 352/719, 352/721, 376/369)
   and rule out 267/638.
5. Page the held index PDFs to restore the 166 Runsheet legal descriptions.
6. Work the Tax Roll for current mineral-owner addresses.
7. Obtain Exhibits A/B/C and the Excluded Assets schedules.

## DELIVERABLES IN THIS PACKET

| Path | Rows |
|---|---|
| `00_CONTROL/CLAUDE_READ_ONLY_ANALYST.txt` | control record |
| `01_INPUT_INVENTORY/SECTION32_V10_INPUT_LEDGER.csv` | 18 |
| `01_INPUT_INVENTORY/V7_WORKBOOK_DUMP.txt` / `V7_WORKBOOK_CLEAN.txt` | 757,657 chars / 1,846 rows |
| `02_MASTER_UPDATE_REGISTER/SECTION32_V10_MASTER_SHEET_UPDATE_REGISTER.csv` | 36 |
| `02_MASTER_UPDATE_REGISTER/SECTION32_TRACT_UPDATE_REGISTER.csv` | 7 |
| `03_CURRENT_OWNER_RESEARCH/SECTION32_CURRENT_OWNER_MASTER.csv` | 87 |
| `04_CURRENT_LEASE_RESEARCH/SECTION32_CURRENT_OGL_MASTER.csv` | 8 |
| `04_CURRENT_LEASE_RESEARCH/SECTION32_TITLE_TO_OGL_COVERAGE.csv` | 87 |
| `05_RUNSHEET_REFRESH/SECTION32_RUNSHEET_ADDITIONS_CORRECTIONS.csv` | 213 |
| `06_WELL_OCC_RESEARCH/SECTION32_CURRENT_WELL_MASTER.csv` | 12 |
| `07_ADDRESS_RESEARCH/SECTION32_ADDRESS_MASTER.csv` | 67 |
| `08_WI_ASSIGNMENT_RESEARCH/SECTION32_CURRENT_WI_MASTER.csv` | 12 |
| `10_PATCH_PACKET/SECTION32_CLAUDE_V10_PATCH_PACKET.csv` | 161 |

**Input ledger SHA-256:** `38c610a8148952f9d78f9be30300563b1dcad79c79234014bf85d193bf7bcc03`
**Patch packet SHA-256:** `87dfcf42eccafc99ad08272e21f459d39b46ab0549d81dfb153644ce4b35c1de`

**Patch decisions:** 147 APPLY · 8 DO_NOT_APPLY · 6 CURATIVE_REQUIRED

No XLSX was created, edited, recalculated, saved, converted, renamed, moved,
overwritten or uploaded by this session.
