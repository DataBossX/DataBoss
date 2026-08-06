# Independent calculation, title-logic, and completeness audit

Date: 2026-07-10 (America/Chicago)

Scope: read-only review of the two workbooks in `FINAL`, `Template.xlsx`, the prior DOCX/PDF report, the evidence register, the earlier draft workbook, Section Notes, plat/tax materials, the source inventory and OCR/classification outputs, selected controlling record images, OCC well/completion data, and the existing rebuild/QA scripts and JSON reports. No deliverable was edited.

## Bottom-line verdict

The stronger **content** candidate is:

`FINAL\32-11N-25W_Beckham_Co_Diversified_Cursory_Title_Report_7-10-26 - NHE.xlsx`

It is stronger because it removes the first candidate's visible old-project postings, replaces the unrelated template plat, adds a conclusion/open-requirement matrix, expands OGL and well context, and more consistently refuses to invent a current Diversified decimal. It is **not** a safe final workbook or a safe rebuild base. It should be treated as a narrative/evidence donor only.

The best production path is a fresh byte copy of `Template.xlsx`, populated from a corrected instrument ledger. Do not continue editing either candidate in place.

### Measurable comparison

| Gate | First `2026-07-10.xlsx` | `7-10-26 - NHE.xlsx` | Verdict |
|---|---:|---:|---|
| Exact 13 sheet names/order | 13/13 | 13/13 | Both pass |
| Formula cells | 4,538 | 0 | Both fail substantively; Template has 5,126 |
| New/changed Section 32 formulas | 0 | 0 | Both fail |
| Missing Template formulas | 588 | 5,126 | NHE intentionally destroys the calculation model |
| Template merges retained | 1,078/1,368 | 39/1,368 | NHE is much farther from Template |
| Missing/extra merges | 290/0 | 1,329/17 | Both fail |
| Required hidden state | WI 2 wrongly visible | WI 2 wrongly visible | Both fail |
| Broken defined names | 21 `#REF!` + stale `_Order1` | same | Both fail |
| External workbook links | 0 | 0 | Both pass |
| Hyperlinks/source links | 0 | 0 | Both fail traceability |
| Runsheet data rows | 49, including duplicate 2476/1 | 46, no duplicate 2476/1 | NHE cleaner but incomplete |
| Stale prior-project transaction postings | extensive | cleared from visible values | NHE materially better |
| Old unrelated PLAT bitmap | retained | removed | NHE better |
| Usable present WI/NRI/NMA conclusion | no | no | Correct result given missing evidence |

The first candidate's 4,538 formulas are not an advantage: every formula is unchanged from Template, and 134 formulas plus 100 constants in transaction-posting regions are unchanged old-project content. The NHE candidate avoids that contamination by deleting the matrix, but deletion is not a substitute for rebuilding the title calculation.

## Accuracy and completeness assessment of the NHE candidate

### What is accurate or appropriately conservative

- The controlling conclusion that the supplied evidence cannot support an exact current Diversified WI, NRI, leasehold decimal, ORRI decimal, mineral/royalty interest, or net acres is correct.
- Full-section index ticks are correctly treated as facial indexing, not 640 NMA or 100% WI.
- The report correctly treats the post-April-1988 copies and schedules as missing and leaves current vesting/HBP open.
- The seven historical arithmetic cross-checks described below are mathematically correct.
- The 11 OGL references in the evidence register all appear on the NHE OGL sheet.
- All eight instruments in the evidence register's `Direct_Diversified` table appear in the NHE Runsheet.
- The surface parcel acreages total exactly 640.00 acres; the workbook correctly says this is surface/nominal context, not a title decimal.
- The purported Tax Roll PDF is correctly identified as a duplicate of the assessor parcel map.

### Why the report is not complete

- There is no ownership/posting calculation model: zero formulas, zero transaction columns, zero subtotals, zero RECHECK controls, and zero summary-to-ledger cross-feet.
- The NHE Runsheet omits known direct-affiliate, financing, countywide-screen, and predecessor-bridge leads documented elsewhere in the same workspace.
- Exact record-image citations are wrong for three material historical instruments, and one effective-date statement contradicts the controlling record image.
- The inventory does not support a claim of exhaustive review: 4,174 of 4,893 record images remain marked `visual review required = YES`; six images have OCR errors; and all 10,053 inventory rows remain `NOT YET REVIEWED` in `source_inventory.csv`.
- The report contains no hyperlinks, no source-cell links, no verified one-instrument-per-row ledger, and no evidence-to-posting reconciliation.
- Known official completion data identifies one additional active Section 32 well that is absent from the report.
- The county index cutoff is 2026-07-01, not the report date of 2026-07-10; no continuation closes that gap.

The appropriate status remains `PROVISIONAL — OPEN TITLE REQUIREMENTS`, not final/complete.

## Critical factual and citation corrections

### P0-1 — Bk 845/P47 cites the wrong images

NHE locations:

- Runsheet row 11 notes `Images 4120-4121`.
- Tract 2 row 5 says `Imgs 4120-4121`.

Correction:

- Bk 845/P47-48, Cities Service Oil & Gas Corp. to Leede Exploration, is in **Images 4118-4119**.
- Images 4120-4121 are unrelated Bk 845/P149-150 probate pages in the Estate of Charlie B. Crook.

This is a direct source-citation error, not a formatting issue.

### P0-2 — Bk 1014/P75 has the wrong effective date

NHE Runsheet row 16 states `effective 1988-01-01`.

The controlling Image 4893 states that the assignment is effective, for all purposes, **as of the date of first production from the Leede Oil & Gas, Inc. McCall #1-29 well**. It does not state a fixed 1988-01-01 effective date.

Correction: replace `effective 1988-01-01` with the quoted conditional effective event, and separately retain execution 1988-02-18 and recording 1988-04-26.

### P0-3 — Bk 872/P279 source range starts two images too early

NHE locations:

- Runsheet row 12 cites `Images 4386-4393`.
- Tract 2 row 6 cites `Imgs 4386-4393`.

Correction: the Bk 872/P279 assignment starts at **Image 4388** and runs through Image 4393. Images 4386-4387 are Bk 872/P153-154 pages from a different exhibit/record.

### P0-4 — Bk 987/P159 source range is overinclusive

NHE locations:

- Runsheet row 14 cites `Images 4840-4857`.
- Tract 2 row 8 cites `Imgs 4840-4857`.

Correction: the assignment/reservation is **Images 4840-4852**. Image 4852 is the final acknowledgement at Bk 987/P171. Image 4853 begins an unrelated deed of trust at Bk 988/P209; images through 4857 belong to that later record.

### P0-5 — `material interest` is unsupported magnitude language

Overview B53, Title conclusion C126, and Tract 5/WI 1 summary B14 call the indexed acquisition a `material interest`. The missing schedules prevent determining magnitude. Full-section indexing establishes geographic indexing, not materiality.

Correction: use `one or more interests/asset entries indexed against Section 32` or `an interest of undetermined estate and quantum`. Retain `material` only if the operative schedule or another competent source proves magnitude.

### P0-6 — `last title-type event has two grantees` is inaccurate

Tract 5 and WI 1 summary C15 says `Last title-type event has two grantees`. The two-grantee event is Bk 2395/P415. The same matrix then shows Bk 2400/P551, a later conveyance to a single grantee, Diversified Production LLC. Separate later branches also exist.

Correction: state: `Bk 2395/P415 created two facial grantee branches; Bk 2400/P551 may move only the DP Sooner branch to Diversified Production LLC; the Diversified ABS VI branch and all later succession remain open.`

## Arithmetic audit

### Supported historical arithmetic — all calculations pass

| Calculation | Recalculation | Result |
|---|---:|---:|
| Bk 509/P220 participant allocation | 64 + 25 + 5 + 4 + 1 + 1 | 100.000% |
| Bk 509/P176 employee ORRI | 1 + 1 + .10 + .10 + .05 | 2.250% |
| Bk 502/P265 Leede royalty/ORRI weights | 21.053 + 52.632 + 5 x 5.263 | 100.000% |
| Bk 903/P50 PRF before-payout LGWI | 3 x .526300 + 98.421100 | 100.000000% |
| Bk 903/P50 PRF after-payout LGWI | 3 x 1.315750 + 96.052750 | 100.000000% |
| Bk 987/P159 McCall reservation | 8.629197% x .5% | .043145985%, shown .043146% |
| Bk 987/P159 Pearl reservation | 10.462093% x .5% | .052310465%, record shown .052310% |
| Surface parcels | 40+40+160+40+40+80+120+67.28+12.72+40 | 640.00 acres |

Required treatment:

- Preserve these as historical, estate-specific calculations.
- Do not carry any of them into current Diversified ownership without a proven successor chain, payout/reversion status, burden survival, and asset schedule.
- Preserve full precision in a calculation ledger; display record precision separately.

### No present-interest arithmetic exists

The NHE workbook has zero formulas. Therefore it does not calculate or reconcile:

- current WI/NRI by tract, wellbore, formation, or branch;
- net acres;
- surviving ORRI burdens;
- owner totals;
- instrument-column grantor-out/grantee-in balances;
- Title totals to tract totals;
- WI sheet totals to Title;
- overlap/non-additivity of Tracts 1-5.

The absence of an invented decimal is correct. The absence of a calculation framework is not.

### Template Title formulas are all missing

The 12 generic total formulas required at the Template coordinates are absent:

- C27, C28
- C50, C51
- C72, C73
- C89, C90
- C112, C113
- C127, C128

In the NHE workbook, C127 and C128 are occupied by narrative confidence-matrix text. The new material at rows 124-151 overwrites the Template's last title/WI calculation block rather than extending it in a controlled attachment.

Do not restore Template E123/E124/E126 automatically; those 1-3/16 formulas are prior-project transaction facts and require independent Section 32 proof.

### Acreage classification

- 160 acres for the NE/4, 80 acres for E/2 SE/4, and 320 acres for N/2 are **nominal legal-area context**, not Diversified net acres.
- Crook is a wellbore/depth estate; its interest cannot safely be summarized as 160 gross or net acres merely because the well is in the NE/4.
- Pearl is wellbore/depth limited; 80 acres is the described E/2 SE/4 area, not current leasehold net acres.
- Tract 4 OGL descriptions overlap and cannot be added.
- Tract 5 full-section ticks cannot be posted as 640 acres, 100% WI, or every depth.

These distinctions should be encoded in separate `Legal Area`, `Gross Acres`, `Interest Fraction`, and `Net Acres` fields, not mixed in one title cell.

## Runsheet audit of the NHE candidate

### Structural/data defects

- 46 populated data rows, rows 2-47.
- Column B `OGL` is blank in all 46 rows.
- Column K is an added Evidence Tier/Confidence column; it is not part of the Template A:J design.
- There are zero true Excel date values in E or F. E has 18 text strings and 28 blanks; F has 46 text strings.
- Nine rows combine multiple instruments and must be split:
  - row 21: 1137/340 and 1140/1;
  - row 22: 1217/304 and 1217/318;
  - row 25: 1346/34 and 1442/270;
  - row 26: 1522/84 and 1522/87;
  - row 27: 1524/36 and 1533/362;
  - row 28: 1577/450, 1581/303, and 1581/319;
  - row 30: 1783/118 and 1784/959;
  - row 32: 2185/639, 2225/1, and 2225/710;
  - row 37: 2371/495 and 2371/514.
- The KeyBank termination at row 47, recorded 2022-11-28 in NHE, is appended after the 2026 entries instead of sorted chronologically.
- Inception rows begin with the 1907 patent and then go backward to 1906/1905 receipts.
- `OPEN — read stamp` is used where a direct image should be read and the recording stamp separately transcribed.
- There are no hyperlinks to the cited local image, index page, public-detail URL, or OCC source.
- Confidence percentages are not tied to a written scoring rubric and should not be treated as arithmetic.

### One-instrument-per-row treatment

Each book/page or instrument number must have its own row. A correction may cross-reference the superseded record, but Bk 471/P330 and Bk 471/P337 should also be logged as separately identified instruments with `superseded/corrected — operative effect controlled by ...` status if they are being relied on.

Execution date, effective date/event, acknowledgement date, and recording date must not be collapsed into one string. Use separate typed fields or put the extra dates in Notes while preserving a true typed execution/effective date and true recording date.

## Missing or incompletely carried instruments

The following are evidence-led leads that must be verified against the high-resolution index/public detail before final posting. They are not permission to assume substantive title effect.

### Direct/affiliate title-event omissions from the NHE workbook

The earlier manually read draft logs 12 modern direct/affiliate events. NHE carries 10 and omits:

- **Bk 2393/P1** — Burlington Resources Oil & Gas to DP Legacy Central LLC, recorded 2022-10-17; broad/full-section index marks; schedule absent.
- **Bk 2475/P943** — Canvas Energy LLC to Canvas Energy II LLC merger/corporate-succession entry, recorded 2026-01-23; required predecessor for Bk 2476/P1.

These omissions also make the Tract 5/WI summaries incomplete.

### Modern financing, release, and collateral leads not carried

The prior report's financing/release reconciliation list includes these book/page anchors:

- 2341/127
- 2342/369
- 2371/439, 2371/554, 2371/589
- 2389/417, 2389/590, 2389/630
- 2395/370, 2395/967, 2395/973
- 2415/410 et seq.
- 2476/67 and 2476/109

NHE carries only 2395/967-972. Every filing must be classified separately as mortgage, fixture filing/UCC, release, termination, amendment, or other; its collateral schedule must be matched to the final lease/asset schedule. Do not infer release of a branch merely from a filing elsewhere in the package.

### Countywide long-description/no-legal screen omitted

The evidence register/draft identifies four later records that cannot be conclusively excluded without their schedules/corporate documents:

- I-2024-002930, Bk 2434/P751-760 — Diversified Production LLC and DP Legacy Central LLC to Teocalli Exploration LLC, wellbore assignment.
- I-2025-003599, Bk 2464/P200-217 — Stephens/Continental affiliates to Diversified Production LLC, wellbore assignment.
- I-2026-001031, Bk 2480/P824-883 — DP Legacy Central LLC and Diversified Production LLC affidavit.
- I-2026-001039, Bk 2480/P903-909 — multiple DP/Diversified/Canvas affiliates merger filing with no indexed legal description.

NHE carries none of these and omits the draft's thirteenth open requirement. Add them to a clearly labeled countywide screen/exceptions portion of Runsheet/Notes until pulled and ruled in or out.

### Predecessor-bridge omissions/conflicts

The prior draft/open-requirement material identifies these additional bridge items that NHE omits:

- Bk 1016/P7, P13, P18, P25, P29, and P33 (NHE carries only P38).
- Bk 1536/P368, a Kabala/Leede branch entry carried in the first candidate and the prior report's bridge list but omitted from the later evidence-register chain.

The conflict over 1536/368 must be resolved against the index, not silently dropped. The entire 1014/76 through 2340/490 bridge should be rebuilt one instrument per row.

### Unrecorded/underlying agreements

The report correctly identifies but does not ledger the referenced agreements dated 7/9/1979, 11/20/1979, 1/7/1980, 2/7/1984, and 3/20/1985, plus Exxon/NICOR/Vinson/White/TCW agreements. Carry them in an `Unrecorded/Referenced Agreements` exception schedule with source instrument and required copy; do not give them book/page values unless proven.

## OGL audit

Positive: all 11 OGL references in the evidence register are present, and gross legal-area values are mathematically consistent with the stated aliquots.

Defects:

- Every recording date is text `OPEN`; all lease dates are text, not true Excel dates.
- Primary term, expiration, net mineral acres, royalty, pooling, Pugh, HBP, extension, warranty, and top-lease status are `OPEN ITEM` on every row.
- `OPEN ITEM` text occupies numeric/date fields, preventing formulas and type validation. Those cells should be blank, with the requirement in Notes.
- The same generic source text is repeated across rows; exact exhibit image/page and source instrument should be cited row by row.
- The OGL numbers are not linked back into Runsheet B or Title D.
- Gross acres overlap and must never be totaled as ownership acreage.

Required label: `LEASE REFERENCE ONLY — ORIGINAL LEASE NOT REVIEWED`. Do not use the table to conclude expiration or HBP until the actual OGL and lease-to-well/unit history are reviewed.

## Well and unit audit

### Missing well

The official completion file `occ_completions_section32_filtered.csv` contains an additional active Section 32 well omitted from NHE and from the evidence-register Wells table:

- API **35-009-21933**, Carlson 32-11-25 #10H, Latigo Petroleum LLC, status AC, gas, Missourian, spud 2014-05-25, completion/first production 2014-09-13, TD 16,499 ft, perforations 11,839-16,187 ft.

It must be added as regulatory context, with the same no-title/no-HBP disclaimer.

### Exact operator-name corrections

Use the official RBDMS strings rather than shortened names:

- `BP AMERICA PRODUCTION COMPANY` instead of `BP America`.
- `SM ENERGY COMPANY` instead of `SM Energy`.
- `LEEDE OIL & GAS INC` instead of `Leede Oil & Gas`.
- `VASTAR RESOURCES INC` instead of `Vastar`.

### Status correction

RBDMS code `EX` means `Expired Permit — expired prior to drilling operations`. NHE's `Expired/other nonactive status` wording for Katie #1-32 should be replaced with the exact data-dictionary definition.

### Incomplete available fields

The RBDMS source includes precise surface quarter/quarter, footage calls, coordinates, status/type, and direct well-record URLs for the 11 legacy rows. NHE reduces every surface location to generic `Section 32...` and has no hyperlinks. The completion file also supports Crook, Twin, and Carlson spud/completion/formation/perforation/TD data. Populate all supported fields; leave genuinely unsupported spacing, order, bottom-hole, last-production, and HBP fields blank/open.

Crook's AC/DRY conflict is correctly flagged. AC means an open, not-plugged wellbore; it is not proof of production or lease perpetuation.

## Plat, tax, and Section Notes

- The ten assessor surface parcels cross-foot to 640.00 acres and form a complete surface mosaic.
- The NHE PLAT sheet removes the old unrelated template bitmap and embeds the two assessor pages. That is useful source context but is not a title tract/depth/branch plat.
- Build a Section 32 4x4 quarter-quarter base with separate overlays for Tract 1 (Crook wellbore/depth), Tract 2 (Pearl wellbore/depth), Tract 3 (N/2 below top Hunton), overlapping OGL coverage, and full-section index-only modern branches. Use hatching/layers so overlapping interests are not shown as mutually exclusive fee parcels.
- The supplied Tax Roll PDF is byte-identical to the assessor map and is not an actual tax roll. Obtain the real tax roll if tax status matters.
- Section Notes establish index certification through 2026-07-01 and last book/page 2490/471 (WD). A 2026-07-10 report cannot claim a 2026-07-10 effective title date without a 7/2-7/10 continuation, including no-legal and UCC central records.

## Template and workbook integrity defects in NHE

- All 5,126 Template formulas are absent.
- 1,329 Template merges are missing; 17 non-Template merges were added.
- Only 39 of 1,368 Template merges remain.
- Every tract/WI sheet has been replaced with an A:H static matrix. This removes the intended transaction columns and owner posting architecture.
- WI 2 is visible although Template hides it.
- All 22 inherited defined names remain: 21 resolve to `#REF!`; `_Order1` is a stale hidden numeric name.
- Runsheet expands to K and Title expands to row 151, departing from the Template design.
- Title conclusion/open-requirement content overwrites calculation rows 124-132, including C127/C128.
- There are no hyperlinks, comments, tables, or data validations.
- Calculation mode is set to automatic/full-calc, but there is nothing to calculate.
- External-link parts, connections, query tables, pivot caches, macros, and calcChain are absent; these are positive package results.

## Review of existing scripts and QA JSON

The existing QA outputs should not be accepted as substantive title or workbook QA.

### `full_qa_audit.py`

- Searches a short stale-word regex but does not compare against Template formulas, merges, posting regions, title totals, or prior-project constants.
- Searches defined names only for stale words; it does not fail 21 `#REF!` defined names or `_Order1`.
- Formula QA only looks for displayed error tokens. Missing formulas and overwritten controls therefore pass.
- Scans limited ranges/rows and does not inspect all right-side transaction cells.
- Does not test one-instrument-per-row, duplicate book/pages, date types, execution-vs-recording support, chronological order, OGL linkage, arithmetic cross-feet, or evidence citations.
- Its `title_risks` flags safe disclaimer text containing `NOT 640 NMA or 100% WI`, producing false-positive risk entries rather than proving a defect.
- `controlling_ok` is false in the saved JSON, but the rebuild log nevertheless characterizes the conclusion as corrected.

### `verify_workbook.py`

- Exit status depends only on stale-token hits. Formula errors do not cause failure.
- Does not require any formulas, merges, controls, defined-name cleanup, hidden state, or source support.
- Counting rows is not completeness reconciliation.

### `qa_rebuild_excel_com.py`

- Unmerges broad ranges and clears only portions of transaction sheets, leaving the P:AD row 21+ contamination proven in the prior forensics audit.
- Writes post-1988 recording dates into both effective and recording columns.
- Adds Runsheet K, writes `OPEN ITEM` into numeric fields, and deliberately makes WI 2 visible.
- Clears Title merges/formulas and replaces totals with narrative.
- Does not delete broken defined names or rebuild a Section 32 posting ledger.
- Adds a duplicate 2476/1 supplemental row and used a conflicting 2395/967 date in the first candidate.

### `finalize_template_report.py` (NHE generator)

- Copies the already-corrupted first candidate rather than a clean Template.
- `rebuild_static_matrix` explicitly unmerges every tract/WI range and clears all formulas.
- Hard-codes the wrong image ranges and Bk 1014/P75 effective date identified above.
- Appends the 2022 termination after 2026 events.
- Uses only the 12-item evidence-register requirements, omitting the draft's countywide-screen requirement.
- `qa_no_legacy_values` is a token scan; it cannot detect missing formulas, broken names, missing instruments, incorrect citations, or unsupported title logic.

The JSON statements `formula_errors: []`, `stale: []`, and `final_open_ok: true` prove only that Excel could open the file and no scanned error token appeared. They do not establish accuracy, completeness, template fidelity, or title reliability.

## Prioritized correction plan

### P0 — Before any workbook rebuild

1. Freeze both FINAL candidates as read-only evidence donors.
2. Create a fresh byte copy of Template.xlsx; remove its two external links and all 22 stale/broken defined names in the working copy.
3. Build a normalized one-instrument-per-row evidence ledger with fields for instrument number, book/page start/end, type, execution date, effective date/event, recording date, grantor, grantee, exact legal/estate/depth/wellbore, reservation/burden, source tier, exact source path/URL, confidence category, and open requirement.
4. Correct the four direct-image citations/effective-date defects listed above.
5. Reconcile every instrument list: evidence register, prior report, earlier draft, both candidates, all 62 index pages, countywide screen, financing list, and post-cutoff bridge. Record each item as included, excluded with evidence, duplicate, superseded, or still open.
6. Manually review the material index pages at native/high resolution and perform alias searches for every Diversified/DP/Tapstone/KL CHK/OCM Denali/Canvas/FourPoint/Unbridled/MNR/Chesapeake/Burlington entity variant. OCR alone is insufficient.

### P1 — Calculation and posting rebuild

1. Clear all prior-project factual/posting content from the fresh Template while preserving styles, print settings, merges, logo, and generic formula architecture.
2. Rebuild tract/WI transaction columns from the normalized ledger. Each completed column requires source, book/page, dates, fraction/estate treatment, grantor-out, grantee-in, subtotal, RECHECK, and evidence tier.
3. Distinguish historical snapshots from current carry-forward. Do not post a carry-forward across a missing instrument or schedule.
4. Restore the 12 generic Title total formulas at their exact Template cells. Do not restore prior-project E123/E124/E126 fractions.
5. Keep numeric/date fields numeric/date or blank; move `OPEN ITEM` explanations to Notes/Evidence.
6. Cross-foot Title to each tract, WI/NRI to WI sheets, and all transaction subtotals to zero after Excel full rebuild.

### P1 — Content completeness

1. Add Bk 2393/P1 and 2475/P943 as qualified index-only events.
2. Add/classify all modern financing/release leads.
3. Add the four countywide-screen records and the thirteenth open requirement.
4. Resolve/add the 1016/P7-P33 entries and 1536/P368 conflict.
5. Add Carlson 32-11-25 #10H and exact official operator/status wording.
6. Link every OGL to the affected runsheet/tract rows and carry all supported historical burdens to the Title notes without implying survival.
7. Add explicit assumptions/exceptions: evidence hierarchy, index-tick limitation, ARTI/assignor-sufficiency limitation, no corporate-deal percentage substitution, no HBP without lease-level proof, cutoff/continuation, and confidence rubric or categorical tier.

### P2 — Template/visual completion

1. Keep exactly 13 sheets in Template order; preserve the trailing space in `Title `.
2. Hide PLAT and WI 2; keep Runsheet within the intended A:J layout or document a formally approved variance.
3. Create an actual layered Section 32 tract/depth/branch plat; retain assessor pages only as ancillary source context.
4. Add working local/public hyperlinks or an exact source-citation convention that survives delivery.
5. Render every sheet, including temporarily unhidden PLAT/WI 2, and inspect page breaks, clipped text, blank pages, legal descriptions, and print areas.

## Mandatory final acceptance gates

- Zero unapproved prior-project factual values or postings.
- Zero `#REF!`/external/stale defined names.
- Exactly 13 Template sheets/order; PLAT and WI 2 hidden.
- Required Template merges/formulas restored or each approved exception documented.
- One instrument per Runsheet row; no combined references or duplicates.
- True typed dates; execution/effective/recording dates separately supported.
- All eight evidence-register direct events, Bk 2393/P1, Bk 2475/P943, financing leads, countywide screen, and bridge conflicts reconciled.
- All 11 OGL references carried and linked; unsupported terms blank/open in Notes.
- All 12 known wells from combined RBDMS/completion evidence carried, including Carlson 10H.
- Every completed transaction column has a supported subtotal and RECHECK; all cross-feet equal zero.
- Excel full calculation/reopen succeeds with no repair prompt and no formula errors.
- Final status remains provisional unless every decisive copy-pull, chain, burden, HBP, and continuation requirement is closed.

## Final QA opinion

The NHE candidate is the best available narrative starting point, but it is not an accurate, complete, Template-equivalent Diversified title report. Its core cautionary conclusion is sound; its supported historical arithmetic is sound; its production workbook structure, source precision, instrument completeness, and reconciliation are not. Use it as a prose/evidence donor to a clean Template rebuild only after the exact corrections above.
