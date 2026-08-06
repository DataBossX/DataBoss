# Workbook forensics: Template.xlsx and the two original Diversified reports

Date: 2026-07-10 (America/Chicago)

Scope: read-only inspection of the three XLSX files that were present in `FINAL` when the audit began:

- `Template.xlsx`
- `32-11N-25W_Beckham_Co_Diversified_Cursory_Title_Report_2026-07-10.xlsx` (the noon report)
- `32-11N-25W_Beckham_Co_Diversified_Cursory_Title_Report_7-10-26 - NHE.xlsx` (the later NHE report)

The source workbooks were not saved, renamed, moved, or edited. Tests used raw OOXML/ZIP inspection, openpyxl, and Microsoft Excel 16 COM in normal read-only open mode. No printer driver or LibreOffice was available, so a final print/PDF render of all sheets remains required.

## 1. File identity and integrity

| File | Bytes | SHA-256 | ZIP test | Excel normal read-only open |
|---|---:|---|---|---|
| Template.xlsx | 527,740 | `fe2fc01613b3bfe627fee0c4b27c2423884bb6f0a3ba7a3e658efab728b87bb9` | PASS | PASS; two external workbook links reported |
| Noon report | 513,991 | `e102112f09ff61d230bb9892d3dec600c331c63406bb0a0673cd9c77e76f7467` | PASS | PASS; no external links |
| NHE report | 642,826 | `3aae381a2297eb4b307d025bd37e69c8e819dd9487e06183e3a8647e2b253b13` | PASS | PASS; no external links |

No file contains a VBA project, embedded OLE object, connection, query table, or pivot cache. No explicit Excel repair error was raised. Excel alerts were suppressed during automation, so the final deliverable should still be opened interactively once to confirm that no repair banner appears.

## 2. Verdict

The later **NHE report is the best of the two Diversified reports as a substantive content lead**, but it is not a finished title report and is not the best structural base for repair.

Why NHE wins the content comparison:

- It removes the verified Roger Mills/prior-project contamination and the old unrelated PLAT bitmap.
- It adds a much fuller conclusion matrix, twelve explicit open requirements, eleven OGL references, a better-qualified post-1988 chain, two static Diversified branch summaries, and materially fuller well context.
- It correctly refuses to state an exact present Diversified WI, NRI, leasehold/ORRI decimal, mineral/royalty interest, or net acres when the operative instruments and schedules are missing.
- It separates the 2395/967 financing termination from the actual 2395/415 conveyance.

Why it is not ready:

- It deletes **every formula in the workbook** and almost the entire template ownership/posting model.
- It deletes 1,329 template merges, adds 17 non-template merges, changes 3,413 cell style arrays, and changes the widths/heights and print behavior of most reporting sheets.
- It is incomplete even against its own evidence register: four countywide Diversified screening items and five modern financing references are absent.
- It contains hundreds of `OPEN` placeholders, no self-contained source legend or source hyperlinks, no current-interest calculation, no chain cross-foot, and multiple date/order/layout defects.

The noon report is closer to the template cosmetically, but it is unsafe as a substantive base. Its 4,538 surviving formulas are all unchanged template formulas, its known old posting regions remain unchanged, it retains the wrong PLAT image, it has 290 missing merges, and it contains verified old-project book/pages, WI denominators, and formation/acreage values. Use it only as a secondary lead list.

**Safe rebuild choice:** make a fresh byte copy of `Template.xlsx`, remove its external links/stale names and prior-project contents, then re-key the supported NHE facts and evidence. Do not repair either Diversified workbook in place and do not copy entire NHE sheets into the template.

## 3. Candidate comparison

| Gate | Template | Noon report | NHE report |
|---|---:|---:|---:|
| Exact 13 sheet names/order | yes | yes | yes |
| Formula cells | 5,126 | 4,538 | **0** |
| Merged ranges | 1,368 | 1,078 | **56** |
| WI 2 hidden | yes | no | no |
| Runsheet used columns | A:J | A:K | A:K |
| Known stale-token hits from the targeted contamination scan | n/a/template source | 17 | **0** |
| Old PLAT bitmap SHA `d1caf98a...` | present | present | absent |
| Direct Diversified evidence entries in the evidence register (8) | n/a | partial/lead prose | all 8 represented |
| Countywide Diversified screening entries in the evidence register (4) | n/a | absent | **all 4 absent** |
| Exact present Diversified decimal | not applicable | not established | not established, correctly disclosed |
| External link parts | 2 links / 4 parts | 0 | 0 |
| Broken custom names | 19 broken plus 2 external | 21 broken | 21 broken |

The noon report's targeted stale hits are:

- Tract 1: `AE3 1826/56`, `AF3 1944/38`, `BF3 2610/574`.
- Tract 2: `AJ3 2610/574`.
- Tract 3: `AO3 2610/574`.
- Tract 5: `AN3 2610/574`.
- WI 2: `D1 All rights to the Springer Formation`, `D4 377.53845154`.
- WI 1: `G10:G16`, `L21`, and `M22` use the old `448.333333` denominator.

The broader prior audit also established unchanged old posting blocks and 234 template-identical posting formulas/constants in the noon report. NHE clears those values, but replaces the model with static tables rather than rebuilding it.

## 4. NHE versus Template: exact sheet structure

Raw dimensions are the worksheet `<dimension ref>` values stored in OOXML. The NHE PLAT and Well dimensions include blank cells created during clearing; Excel's effective used ranges stop earlier.

| Sheet | Raw dimension Template -> NHE | State Template -> NHE | Formulas T -> N | Merges T -> N | Freeze T -> N | Print area Template -> NHE |
|---|---|---|---:|---:|---|---|
| Overview | A1:AJ56 -> A1:AJ56 | visible -> visible | 0 -> 0 | 30 -> 30 | none -> none | A1:AH57 -> A1:AH57 |
| Title  | A1:G132 -> A1:G151 | visible -> visible | 15 -> 0 | 12 -> 4 | none -> none | A1:G132 -> B1:G151 |
| OGL | A1:AB29 -> A1:AB29 | visible -> visible | 0 -> 0 | 0 -> 0 | A2 -> A2 | none -> A1:AB12 |
| PLAT | B6:AF20 -> A1:AN50 | hidden -> hidden | 0 -> 0 | 8 -> 8 | none -> none | none -> none |
| Runsheet | A1:J145 -> A1:K145 | visible -> visible | 0 -> 0 | 0 -> 0 | A2 -> A2 | A1:J145 -> A1:K47 |
| Tract 1 | A1:GG208 -> A1:GF208 | visible -> visible | 816 -> 0 | 198 -> 2 | G1 -> A5 | none -> A1:H13 |
| Tract 2 | A1:GF210 -> same | visible -> visible | 790 -> 0 | 193 -> 2 | G1 -> A5 | none -> A1:H12 |
| Tract 3 | A1:GF212 -> same | visible -> visible | 781 -> 0 | 193 -> 2 | G1 -> A5 | none -> A1:H11 |
| Tract 4 | A1:FP191 -> same | visible -> visible | 689 -> 0 | 180 -> 2 | R1 -> A5 | none -> A1:H11 |
| Tract 5 | A1:GF212 -> same | visible -> visible | 781 -> 0 | 189 -> 2 | G1 -> A5 | none -> A1:H16 |
| WI 2 | A1:FR145 -> A1:FQ145 | **hidden -> visible** | 598 -> 0 | 182 -> 2 | G1 -> A5 | none -> A1:H12 |
| WI 1 | A1:FX166 -> same | visible -> visible | 656 -> 0 | 183 -> 2 | G1 -> A5 | none -> A1:H16 |
| Well 1 | A1:Q5 -> A1:Q20 | visible -> visible | 0 -> 0 | 0 -> 0 | none -> A3 | none -> A1:Q13 |

The trailing space in `Title ` remains intact. The active sheet remains Runsheet. No additional hidden or very-hidden sheets exist.

### Merges

- NHE preserves all 30 Overview merges and all 8 PLAT merges.
- On Title it preserves only `B2:G2`; it removes the other 11 template merges: `C4:G4`, `C5:G5`, `C31:G31`, `C32:G32`, `C54:G54`, `C55:G55`, `C75:G75`, `C76:G76`, `C92:G92`, `C93:G93`, and `B132:G132`.
- NHE adds three Title merges: `B124:G124`, `B135:G136`, and `B138:G138`.
- On every Tract/WI sheet it removes **every** template merge (1,318 ranges total) and adds only `A1:H1` and `A2:H2` on each of seven sheets.
- Overall, only 39 of 1,368 template merges survive; 1,329 template merges are missing and 17 NHE-only merges exist.

### Formulas and calculation chain

- Template formulas: 5,126, with a matching 5,126-entry calc chain.
- NHE formulas: 0; `xl/calcChain.xml` is absent.
- All 15 Title formulas are removed, including the 12 tract/leasehold total formulas at C27/C28, C50/C51, C72/C73, C89/C90, C112/C113, and C127/C128.
- All 5,111 Tract/WI formulas are removed, including owner totals, grantor-out/grantee-in postings, subtotal formulas, RECHECK controls, and cross-foot logic.
- NHE sets `calcMode=auto`, `fullCalcOnLoad=true`, and `forceFullCalc=true`, but those settings have no practical effect because no formulas remain.
- There are no formula-error literals or cached error values in NHE. That is not a substantive pass: the model that could produce a cross-foot error has been deleted.

## 5. Cell-value differences

The comparison treats `None` and empty string as blank and compares every coordinate inside the union of each sheet's dimensions. There are **9,523 value differences** between NHE and Template.

| Sheet | Same nonblank | Template-only | NHE-only | Different nonblank values | Total value differences |
|---|---:|---:|---:|---:|---:|
| Overview | 21 | 1 | 3 | 16 | 20 |
| Title  | 16 | 359 | 141 | 101 | 601 |
| OGL | 18 | 169 | 97 | 210 | 476 |
| PLAT | 0 | 8 | 1 | 0 | 9 |
| Runsheet | 7 | 833 | 94 | 342 | 1,269 |
| Tract 1 | 0 | 1,179 | 41 | 33 | 1,253 |
| Tract 2 | 0 | 1,026 | 36 | 30 | 1,092 |
| Tract 3 | 0 | 1,047 | 34 | 24 | 1,105 |
| Tract 4 | 0 | 862 | 35 | 23 | 920 |
| Tract 5 | 0 | 1,032 | 59 | 39 | 1,130 |
| WI 2 | 0 | 611 | 41 | 25 | 677 |
| WI 1 | 0 | 680 | 49 | 49 | 778 |
| Well 1 | 12 | 0 | 187 | 6 | 193 |
| **Total** | **74** | **7,807** | **818** | **898** | **9,523** |

Most Template-only Tract/WI values are formulas and Roger Mills sample facts that should not be retained. The material defect is not that NHE changes the facts; it is that NHE abandons the template's transaction-posting and verification structure instead of repopulating it with Section 32 facts.

## 6. Styles, dimensions, hidden columns, and views

Workbook style tables:

| Style component | Template | NHE |
|---|---:|---:|
| Cell style records | 408 | 586 |
| Fonts | 53 | 68 |
| Fills | 18 | 24 |
| Borders | 105 | 106 |
| Alignments | 25 | 25 |
| Custom number formats | 7 | 8 |
| Named styles | 11 | 11 |

Across styled/nonblank coordinates there are 3,413 cell style-array differences, 258 row-height/hidden differences, and 118 column-width differences.

| Sheet | Cell style differences | Row height/hidden differences | Width differences | Newly hidden columns |
|---|---:|---:|---:|---:|
| Overview | 19 | 2 | 0 | 0 |
| Title  | 229 | 46 | 6 | 0 |
| OGL | 336 | 19 | 28 | 0 |
| PLAT | 1 | 0 | 0 | 0 |
| Runsheet | 522 | 136 | 11 | 0 |
| Tract 1 | 307 | 9 | 8 | 180 (I:GF) |
| Tract 2 | 295 | 4 | 8 | 180 (I:GF) |
| Tract 3 | 281 | 5 | 8 | 180 (I:GF) |
| Tract 4 | 273 | 12 | 8 | 164 (I:FP) |
| Tract 5 | 332 | 5 | 8 | 180 (I:GF) |
| WI 2 | 286 | 4 | 8 | 165 (I:FQ) |
| WI 1 | 327 | 4 | 8 | 172 (I:FX) |
| Well 1 | 205 | 12 | 17 | 0 |

All seven Tract/WI sheets are reduced visually to A:H; **1,221 right-side columns are newly hidden**. The old template grid still determines the raw used range and file bulk even though its contents were cleared.

Exact principal width changes:

- Title A:G, Template: `8.4258, 42.8555, 13.2852, 11, 10.5703, 10.4258, 29.7109`; NHE: `8.4258, 32, 26, 23, 18, 31, 66`.
- Runsheet A:K, Template: `8.7109, 7, 18.1406, 11, 12.5703, 11.5703, 41.7109, 48.8555, 49, 56.2852, 28.7109`; NHE: `7, 8, 25, 28, 31, 22, 44, 53, 48, 88, 40`.
- Every Tract/WI A:H becomes `24, 22, 22, 21, 34, 42, 65, 27`; the template A:G base is generally `20.1406, 9, 17.2852, 50.2852, 15, 5.1406, 14.4258`, with H varying by instrument.
- OGL changes all 28 widths; the total width rises from 397.54 to 608 column-width units.
- Well changes all 17 widths; the total rises from 306.11 to 414 units, with Q expanding from 22.8555 to 75.

Critical row-height changes:

- Overview row 53 loses its template height 27; row 55 changes from default to **409.5**.
- Title changes 46 row heights; conclusion rows 126:133 are 48 and open-requirement rows 140:151 are 58.
- OGL rows 2:12 become 58.
- Runsheet rows 2:47 become 54, while many cleared rows retain non-template heights; 136 rows differ.
- Well rows 3:13 become 54.

View differences:

- NHE turns gridlines off on all 13 sheets; the template hides them only on PLAT.
- Overview, Title, OGL, Runsheet, and PLAT otherwise retain their view type/zoom and freeze behavior.
- Every Tract/WI selection pane changes from the template's right pane to a bottom-left pane because the freeze point changes to A5.
- Workbook/sheet protection remains absent and tab colors remain absent.

## 7. Print and page-layout differences

Margins and headers/footers are unchanged on every sheet. The only nonblank header/footer is the Title odd footer: left `New Horizon Energy`, center `Page &P of `, right `405-203-8570`.

- Overview remains portrait/legal, centered horizontally, fit-to-page, and A1:AH57.
- PLAT remains portrait/legal with no print area.
- Title remains portrait/legal at scale 80, adds fit-to-width 1, changes print area from A1:G132 to B1:G151, and keeps manual breaks after 29, 102, and 129.
- Runsheet remains landscape/legal at scale 64, adds fit-to-width 1, changes print area from A1:J145 to A1:K47, and keeps breaks after 26, 41, 69, 93, 112, 131, and 138. Breaks after 47 are stale; K is now intentionally printed but is non-template.
- OGL changes from unspecified page setup/no print area to landscape, fit-to-width 1, print A1:AB12; paper size remains unspecified.
- Every Tract/WI changes from portrait/no print area to landscape legal, fit-to-width 1, and a small A:H print area.
- Well changes from unspecified page setup/no print area to landscape, fit-to-width 1, print A1:Q13; paper size remains unspecified.

Visual consequences requiring correction:

- Overview B53:AH53 and B54:AH54 are merged, but **B55 is not merged**. The 221-character priority-copy paragraph is placed in narrow B55 and compensated with row height 409.5. This is the known one-character/very narrow wrapping defect and can consume most of the legal page.
- Title's unchanged break after row 129 splits the newly added conclusion matrix between C4 and C5. The old break plan was not rebuilt for rows 124:151.
- Title B:G has about 196 width units versus 118 for template B:G and is forced onto one portrait page; OGL is 608 units and Runsheet 394 units on one landscape page. Text is at material risk of being unreadably small.
- Many long tract headers no longer use the template merges, so text relies on overflow/wrap rather than the intended bordered merged blocks.
- No all-sheet print render was possible in this environment; clipped text, page count, and font size remain mandatory interactive QA gates.

## 8. Tables, filters, validations, comments, hyperlinks, and protection

Both Template and NHE have:

- zero Excel tables;
- zero data validations;
- zero conditional-formatting rules;
- zero charts;
- zero cell comments/notes;
- zero cell hyperlinks;
- zero sheet protection and no workbook protection.

Template has no active worksheet `<autoFilter>` elements, although it contains three stale hidden `_FilterDatabase` names. NHE creates active auto-filters on ten sheets: OGL, Runsheet, all seven Tract/WI sheets, and Well 1. It creates no filter on Overview, Title, or PLAT.

The absence of hyperlinks is a substantive usability defect in NHE: cells cite `P-001`, `L-001`, `S-002`, `C-001`, `O-001`, and similar IDs, but the workbook contains no source legend or link target that lets a reviewer resolve those IDs.

## 9. Defined names, external links, and package-level changes

### Template names

Template has 28 raw defined-name records:

- 22 custom names: 19 already equal `#REF!`; `check5` and `XXXXXX` refer to two external workbooks; hidden `_Order1` equals `255`.
- three print areas: Overview, Title, and Runsheet.
- three stale hidden filter-database names.

The two external workbooks are old Grant County and Cimarron County files under an `emorris` OneDrive path.

### NHE names

NHE has 44 raw defined-name records:

- the same 22 custom names, now **21 `#REF!` names plus hidden `_Order1=255`**;
- 12 print-area names;
- 10 filter-database names.

NHE has no external-link parts or LinkSources, but the broken custom names were not cleaned up. Delete all 22 stale custom names unless a name is deliberately rebuilt and proven necessary.

### OOXML/package changes

- Template has 56 ZIP entries; NHE has 30.
- Openpyxl's save converted shared strings to inline strings and removed `sharedStrings.xml`.
- NHE removes Template's calc chain, four external-link XML/relationship parts, and eleven printer-settings binary parts.
- NHE removes the SVG alternate/fallback for the Overview logo.
- Style and media content make NHE's uncompressed package larger despite fewer parts.
- NHE core properties change creator/last modified by to New Horizon Energy and add title/subject. The retained `lastPrinted=2025-01-15` predates NHE's stated creation date of 2026-07-10 and should be cleared or updated.

## 10. Images and drawings

Template has two drawing objects:

1. Overview logo, anchored from K1 to approximately X3, with a 2500x1562 PNG fallback and a 9,824-byte SVG alternate.
2. Old PLAT PNG, 199x199, SHA-256 `d1caf98ae73e3bbb5f9bbaddee6e1410310b2e8c8f0d9146dee13b1847927581`.

NHE has three raster image objects:

1. Overview logo at the same anchor, but only a 2400x1500 PNG remains; PNG hash is `d2772b2865e22e1534e0dd397f4abb12d95deafb5920fb8da8a0bec3e5123869`. The high-quality SVG fallback is lost.
2. PLAT page 1, 1224x1584 JPEG, scaled to 760x983 pixels, anchored A1; SHA `b2cc885336817910775e5b42115525dd821f8dc30cea4ae7cb540d5a19aafcdf`.
3. PLAT page 2, 1224x1584 JPEG, scaled to 760x983 pixels, anchored T1; SHA `d7fca48fecc821ed9f9b091babde2b40eab2c52d7c37ec228d9773470943728d`.

The old wrong PLAT bitmap is correctly absent. However, the replacements are two assessor parcel-map/account-list pages placed side-by-side, not a template-style mineral/leasehold tract plat. The disclaimer is in A40 while the first 983-pixel image extends from A1 through roughly row 49, so the cell text is likely behind/under the image. There is no print area or tract overlay legend.

## 11. Content accuracy and completeness of NHE

### What is materially better/correct

- Section/township/range/county are consistently 32-11N-25W, Beckham County, Oklahoma.
- The report clearly distinguishes a nominal 640-acre section from a 640-net-acre or 100%-WI conclusion.
- It identifies the direct-image cutoff as Bk 1014/P75, recorded 1988-04-26, and the section-index certification date as 2026-07-01.
- It carries all eight `Direct_Diversified` entries in the evidence register: 2371/470, 2371/533, 2389/500, 2389/581, 2395/415, 2400/551, 2451/4, and 2476/121.
- It carries the eleven direct-image pre-1988 chain items and eleven lease references, with appropriate warnings that later schedules/original leases were not reviewed.
- It avoids asserting a current exact interest and explicitly identifies source-title, payout/reversion, lease-HBP, entity-vesting, and branch-overlap issues.
- It flags the Crook well's `Dry` versus `AC` status conflict instead of silently choosing one.

These are internal consistency findings. This workbook audit did not independently re-abstract every source image, so the stated 90%-100% confidence figures are not independently validated by this pass.

### Decisive incompleteness

NHE is a qualified research summary, not a complete title report:

- exact present Diversified WI/NRI/net acres/royalty/ORRI and current vested entity remain undetermined;
- all operative post-April-1988 copies and schedules remain absent;
- the 1988-2020 predecessor chain is index-only;
- original OGL terms and lease-by-lease HBP are unreviewed;
- mineral/royalty and patent inception are incomplete for three quarters;
- liens, payout/reassignment, unrecorded agreements, and entity succession remain open;
- no courthouse continuation after 2026-07-01 is included.

The report uses `OPEN ITEM` exactly 166 times and contains 320 cells with an `OPEN` token. Many are proper warnings, but numerous placeholders are placed in fields that should be blank/typed:

- OGL has 121 exact `OPEN`/`OPEN ITEM` field placeholders: 11 each in Recording Date, Primary Term, Expiration, Net Mineral Acres, Royalty, Pooling, Pugh, HBP, Extension, Warranty, and Top Lease.
- Well has 89 exact `OPEN` field cells plus one `not established` narrative field. Bottom-hole location, spacing, MU order, and last production are open for all 11 wells; most formation, spud, perforation, TD, completion, and plugging facts remain open.
- Title places `OPEN ITEM` text in Net Acres cells C8:C10, C35:C36, C58:C59, C80:C81, C97:C101, and C119:C121. Numeric fields should be blank; status belongs in the evidence/status column.

### Missing instrument/evidence groups

The companion evidence register contains records that NHE does not carry into any sheet:

| Missing group | Evidence-register location | Exact omitted records |
|---|---|---|
| Countywide Diversified screening | `Countywide_Screen` rows 2:5 | 2434/751-760 (2024-002930), 2464/200-217 (2025-003599), 2480/824-883 (2026-001031), 2480/903-909 (2026-001039) |
| Modern blanket financing | `Burdens` row 9 | 2341/127, 2371/554-589, 2389/590-630, 2415/410 et seq., 2476/67-109 |

The four countywide items are not proven to affect Section 32, but they are explicitly Diversified/DP-related and must appear as `COUNTYWIDE SCREEN — SUBJECT APPLICABILITY OPEN`, not disappear. The five financing references must appear in the Runsheet/burden treatment with exact classification and release status. NHE includes the 2395/967 termination but not this broader financing set.

The evidence register also has a 30-row Sources sheet and an eight-row QA sheet. NHE imports the source IDs and some conclusions but not the source directory or QA/cross-foot evidence, so it is not self-contained.

### Runsheet defects

- 46 data rows, but OGL column B is blank in all 46.
- Every populated execution/recording value is stored as text, not an Excel date. Execution/effective date is populated in only 18 rows; recording date is text in all 46.
- Six direct-image rows still say `OPEN — read stamp` in recording date: rows 6, 7, 8, 9, 13, and 15. Those should be resolved by re-reading the cited images or noted as illegible with a reviewer/date.
- At least three clear chronological inversions exist: the 1907 patent precedes 1906/1905 receipts (rows 2:5), and the 2022-11-28 termination is appended after 2026-01-23 (row 47). May 1988 rows are not precisely dated and cannot be reliably sorted.
- Eleven book/page cells bundle more than one instrument: rows 6, 7, 21, 22, 25, 26, 27, 28, 30, 32, and 37. Two are correction/superseded pairs; nine combine distinct indexed entries. Use one instrument per row with a Related Instrument field/note.
- Source IDs/confidence are in K, which is non-template. To match Template, put tier plus exact source citation in J and return the Runsheet to A:J.
- Confidence percentages such as `99% metadata / 25% title effect` have no rubric in the workbook and create false precision. Add a defined rubric or use High/Medium/Low separately for identity, completeness, and substantive effect.

### OGL defects

- Eleven references are present, but OGL/LH cross-references are blank and Title OGL-number fields are blank.
- Every lease/recording date is text; all recording dates are `OPEN`.
- `Garretts`, `Union`, and other party names are abbreviated rather than reproduced exactly from the record.
- Gross Acres is calculated from aliquot descriptions even though the original leases were not reviewed. Label these as `nominal calculated acres (assumption; non-additive)` or leave the lease gross-acre field blank.
- All 28 columns are forced to one landscape page; readability is doubtful.

### Title/Overview defects

- `material interest` in Overview B53 and conclusion C1 is stronger than the available index/schedule evidence supports. Replace with `one or more interests appear in grantee-side index/metadata; estate and quantum open`.
- Report-total rows are narrative and blank rather than formula-driven. Tract totals no longer sit in the template's designated total rows.
- Tract 4/5 headings are shifted to rows 76/77 and 93/94 rather than template rows 75/76 and 92/93.
- Template Notes merge B132:G132 is repurposed as conclusion C7, and the critical copy-pull list is put into the defective Overview B55 cell.
- Examiner identifies only the organization, not an individual examiner/reviewer and review date.

### Well defects

- `Current Listed Operator` and status have no stated dataset-as-of date in the sheet and no row-level source link.
- Surface Location is the generic section description for every row, not an actual surface-location aliquot/coordinates field.
- The template's Plugging column is repurposed to OCC Status, so plugging facts are not captured as their own field.
- Crook remains simultaneously `Dry` and `AC (dataset anomaly)`; this is transparently flagged but unresolved.
- Regulatory status is properly disclaimed as not title/HBP proof, but lease-to-well/unit/order/production matching remains wholly open.

## 12. Required assumptions and qualification language

Any rebuilt report should state these assumptions expressly:

1. Aliquot acreages are nominal calculations, subject to survey, lots, exceptions, metes-and-bounds tracts, and overlapping estates; they are not net mineral acres.
2. Section-wide index checkboxes/long descriptions show only facial legal coverage, not 100% WI, 640 NMA, every depth, or schedule inclusion.
3. `Diversified-affiliated` is an entity-name/transaction-structure inference; it is not proof that every DP-named entity is a title successor or that interests merge.
4. Post-1988 rows based on index/public metadata establish identity/classification only; conveyance terms, schedules, exclusions, depth, fractions, warranties, and after-acquired-title effects remain unreviewed.
5. Historical WI/NRI/ORRI figures are snapshots limited by wellbore, depth, payout, reversion, and burden provisions and are not carried forward as current.
6. Well/operator/status data are regulatory context as of the source-download date and do not prove current production or lease HBP.
7. Countywide long-description/corporate instruments are screening leads until schedules establish Section 32 applicability.
8. No negative mineral/royalty conclusion may be drawn from an incomplete fee/mineral chain.

## 13. Repair priority and acceptance gates

1. Start from a byte copy of Template; preserve exact sheet objects/order/names, Overview logo/SVG, print settings, header/footer, and required merges.
2. Remove both template external links, all 22 stale custom names, old PLAT bitmap/labels, Roger Mills facts, and every prior-project posting value/formula that is not generic structure.
3. Rebuild the seven Tract/WI sheets as the template transaction matrix, not static A:H summaries. Recreate supported instrument columns, owner posting formulas, subtotals, RECHECK controls, and cross-foot logic. Keep unsupported numeric cells blank.
4. Restore Title's tract blocks/merges and designated total logic; place conclusions/open requirements in a template-compatible notes appendix or separate controlled continuation, not by destroying total/note rows.
5. Rebuild Runsheet A:J, one instrument per row, true typed dates, chronological order, OGL cross-references, and tier/source citation in J. Add the four countywide screens and five financing references.
6. Rebuild OGL with one reference per row, exact party names, nominal-acre assumptions, typed dates where proved, blank unsupported fields, and cross-links to Title/Runsheet.
7. Add a self-contained source/evidence legend and row-level resolvable citations without adding an unauthorized sheet if exact 13-sheet identity is mandatory; cell comments or a controlled Title/Overview appendix are options.
8. Replace the PLAT layout with a readable Section 32 tract/estate overlay; keep the assessor pages as ancillary source images, not the title plat. Ensure the disclaimer is visible and outside the image anchor.
9. Resolve source-readable dates, Crook status, well locations/orders/production as far as official evidence supports, and document every remaining open item.
10. Save through Excel, calculate fully, reopen normally, and verify zero errors, zero broken names/links, exact hidden states, print areas, page breaks, formulas, merges, and cross-foot failures.
11. Render and inspect all 13 sheets, temporarily unhiding PLAT and WI 2. Verify no clipped text, microscopic fit-to-page output, image overlap, one-character wrapping, blank pages, or stale hidden content.

Current NHE status by gate:

| Gate | Result |
|---|---|
| Exact sheets/order/name spelling | PASS |
| Required hidden states | FAIL: WI 2 visible |
| Runsheet A:J | FAIL: K used/printed |
| Template formula model | FAIL: 0/5,126 formulas |
| Template merge structure | FAIL: 1,329 missing; 17 extra |
| Known stale content set | PASS in NHE |
| Broken defined names | FAIL: 21 `#REF!` + stale `_Order1` |
| External links/connections | PASS |
| ZIP and Excel open | PASS |
| Source self-containment | FAIL |
| All evidence-register Diversified screens/financing | FAIL: nine groups omitted |
| Exact present interest/current vesting | OPEN / not determinable |
| Runsheet typed dates/order/one instrument per row | FAIL |
| OGL completion | FAIL |
| Well completion | FAIL |
| PLAT/title-map quality | FAIL |
| Full visual print QA | NOT COMPLETED; environment limitation |

Bottom line: NHE is the strongest research/content source of the two reports, but its substantive completeness is provisional and its template/Excel implementation is a failed gate. A final report should be rebuilt from Template and remain explicitly `PROVISIONAL — OPEN TITLE ITEMS` until the operative copies, schedules, continuation, lease/HBP evidence, and current-vesting chain are closed.
