# 31-12N-24W Roger Mills Co. — Cursory Title Report (7-1-26) — NHE — Claude FINAL: AUDIT LOG

**Prospect 25-004 · Section 31-12N-24W, Roger Mills County, Oklahoma · 637.42 gross acres · 10 tracts · Alexander 1-31 (API 35-129-22925)**
Prepared 7/3/2026 by Claude. Companion file: `31-12N-24W Roger Mills Co. Cursory Title Report (7-1-26) - NHE - Claude FINAL.xlsx` (attached in chat; committed to DataBossX/DataBoss branch `claude/roger-mills-title-analysis-cjr34a`; this log saved to the Drive folder — see §8 re: the xlsx binary).

This is the second, deeper pass. It adds full OCR of the 88-page county index PDF, a parsed instrument database, and a documented source-in gap-resolution sweep on top of the first pass.

---

## 1. Base workbook and file lineage (format truth)

Every file in the Drive folder and `files10.zip` was inventoried and diffed cell-by-cell.

| File | Role | Finding |
|---|---|---|
| `...NHE.xlsx` (Drive, 1,559,615 B) | Mission target | Binary download blocked by session egress policy (§8); byte-lineage matches NHE2 |
| `...NHE2.xlsx` (files10.zip, 1,563,970 B) | **Chosen base (format truth)** | Highest-fidelity copy of the examiner's 7-1-26 original: retains the Overview SVG map layer, all 12 legacy comment parts + 11 threaded-comment parts, original VML. Overview plat already carries the corrected tract layout (verified identical to the Corrected Overview Plat workbook). |
| `...NHEbyfable.xlsx` | Prior AI pass | openpyxl round-trip (lost SVG + threaded comments); its data changes were audited change-by-change — adopted where verified, rejected where corrupt (§4). |
| Support workbooks (Copy, Tract QC/fixed, WI cleaned, OGL Completed, Corrected Overview Plat) | Leads | Cross-checked; byfable already superseded them. |
| `project_notes_updated.xlsx` | Directives | Exclusion rule + casing conventions + okcountyrecords API key. |
| `12N 24W 31 - Index.pdf` (88 pp) | **County index — fully OCR'd this pass** | Pages 1–22 handwritten historical numerical index (pre-2000, leads); pages 24–88 = the typed 65-page Roger Mills County Clerk's Unplatted Legal Index Report, date range 02/08/2000–05/05/2026. Machine-printed and reliable. |

The FINAL workbook is produced by **surgical XML editing of the NHE2 base**: media, drawings, comments (legacy + threaded), merges, print settings, tab order and defined names are **byte-identical** to the original. Only the 18 worksheet XMLs, `styles.xml` (highlight changes) and `workbook.xml` (`fullCalcOnLoad`) differ. No tabs added/removed/renamed; no comments added or removed.

## 2. Index PDF OCR + instrument database (new this pass)

All 88 pages were rasterized at 250 dpi and OCR'd (Tesseract 5). The typed Unplatted Legal Index (pages 24–88) was parsed into a structured instrument database: **519 unique instruments**, each with document number, type (O/L, ASGT, MD, QCD, WD, AFF, Order, Decree, REL MTG, MTG, ROW, SUB…), grantor, grantee, book/page, and legal calls for Section 31-12N-24W, 2000–2026. The handwritten numerical index (pages 1–22) was OCR'd as leads for the pre-2000 chain. This database was used to (a) corroborate the Runsheet/OGL, and (b) run the source-in gap sweep in §3. OCR text is retained in the proof folder (`pdf_ocr/`), the parsed database in `index_records.json`.

## 3. Source-in gap resolution sweep (Phase 2) — 29 highlights resolved, 67 preserved

For every one of the 96 pre-existing yellow gap highlights, I ran the full Phase-2 search: earlier **grantee-side appearances in the Runsheet** (col H) under all name/OCR variants, the parsed index database, rawdata, and current-owner lists. The prior pass had missed a set of name-variant matches. Where the **same party is documented acquiring the interest (as grantee) before conveying it out**, via a title-type instrument, the highlight is resolved and removed (per the HIGHLIGHT RULE: "Remove every existing yellow gap highlight that your search resolves"). Resolution detail lives here in the log rather than in-cell, to honor the no-notes lock and avoid corrupting name cells.

**Resolved (highlight removed) — 29 cells, 11 parties, each with a documented source-in:**

| Party | Source-in (grantee-side) | Cells de-highlighted |
|---|---|---|
| Hazel A. Hamilton | Mineral Deed 1978-002576, Bk 237/367 (grantee) | Tract 2 D16 |
| Billy W. Bain (a/k/a Billy Wayne Bain) | Mineral Deed 1978-002585 Bk 237/376; Trust Agmt 1983-001668 Bk 512/61 (grantee) | Tract 2 D22; Runsheet G95 |
| Gregory J. Winneke | Mineral Deed 1982-011143, Bk 480/71 (grantee); confirmed 2012-004060, 2019-001747 | Tract 2 D26; Tract 3 D107; Runsheet G349 |
| Bary Ellen Sitzman | Mineral Deed 1987-005625, Bk 913/261 (grantee, from Billy N. Bein) | Tract 2 D41 |
| Cimarron Mineral Corporation | Assignment 1987-003826, Bk 897/244 (grantee; acquired before 1988-005620 conveyance) | Tract 3 D44; Tract 4 D51; Tract 7 D40; Tract 10 D43; Runsheet G137 |
| Koala Production Company | Mineral Deeds 2004-005738 & 2004-005739, Bk 1764/344-345 (grantee from Sandra York; before 2005-004044 conveyance) | Tract 4 D101; Tract 5 D101; Tract 9 D36; Runsheet G327 |
| Glenn D. Mitchel | Mineral Deed 1949-001867, Bk D63/97 (grantee); Order 1990-006747 Bk 1176/54 confirms 1/3 (before 1981-005180 conveyance) | Tract 3 D37; Tract 4 D32; Tract 7 D33; Tract 10 D31; Runsheet G82 |
| Lola F. Richards | Mineral Deed 1999-003363, Bk 1583/391 (grantee; inherited via Opal Fuchs estate AoH 1999-003362; before 2007-001374 conveyance) | Runsheet G400 |
| Keri Lee Daigle Trust | Mineral Deeds 2011-005695 Bk 2092/134 & 2011-008366 Bk 2108/102 (grantee, 33.3% from Johnson/Sorenson family) | Tract 10 D108; Runsheet G543 |
| Mitchell Buonaccorsi Living Trust | Mineral Deed 2024-007338, Bk 2600/472 (grantee, from Carrie Leeann Mitchell; Runsheet row 528) | Tract 1 D32; Tract 10 D160; Runsheet G546 |
| Michael Best et al / Crouse Family Trust | Order 2001-000618, Bk 1634/353 (probate distribution of Crouse estate; same-day QCD 2001-000619 into the Crouse Family Trust) | Tract 3 D142; Runsheet G243 |

**Preserved (67 highlights) — genuinely unresolved source-in gaps.** These are overwhelmingly root-of-title mineral owners whose acquiring instrument predates the available records (the typed index only reaches 02/08/2000; the pre-2000 handwritten numerical index does not carry a clean earlier grantee-side deed for them): e.g. H.L. Rowley (1916), Shotwell/Hambrook (1931), Elvin & Dorothy Ridling (1953 WD), L.E. & Veronica Thurman (1974 MD — a later 2014 same-surname acquisition does **not** back-fill the 1974 conveyance), Elmo & Freeda Kirk (1976), Charles O. Burckhalter, Federal Deposit Insurance Corp, Alfred William Standiford (1989 conveyance predates the 1994 decree), Mary Margaret Devenas/Wilson, Estate of Barbara Fasken, Oleta Flanagan, Jon N. Wilkerson, Payday Holdings LLC, Onigbe Consulting LLC, Sandra Lorraine York (2005 decree postdates her 2004 lease — kept conservative), Cimarron's downstream, Jesse Joe Newell, etc. Each requires the specific prior vesting instrument (pre-2000 deed, probate decree, or heirship affidavit) pulled from okcountyrecords/the physical grantor index — unreachable from this session (§8). No highlight was added; none removed without a documented source-in.

## 4. Changes applied (workbook edits, ~3,045 cell operations + 29 highlight removals)

Same as the first pass, summarized (full detail retained):
- **Title (space-suffix tab):** OGL references normalized to register numbers only — 21 Bk/Pg lease citations stripped from col G; base-OGL numbers reconciled to the register (D32/D119–121 → 24; D55/D59/D110 → 2); C110 → 75.34; tract-total SUMIF ranges extended to $10:$203; WI-section TBDs replaced with the sheet's N/A conventions; B78 restated. All cited OGL numbers verified present in the register (1–69); no legacy 109–114.
- **OGL:** register identity untouched; data columns K–Y completed (title-carried NMA via live `'Title '!C` links); D37 → Ratification; Q37 → 0.1875; header flags P1:V1 (complete columns) de-highlighted.
- **Runsheet:** duplicate tail rows 566–573 cleared; excluded easement-option (2007-003914) and mortgage partial-release (2012-001856) rows cleared (rawdata retains awareness); phantom OGL 70/71 cross-refs B526/B527 cleared.
- **Tract 1–10:** NET ACRES col C rewritten to the pro-rata SUMIFS convention (every tract foots to gross; ties to 637.42); row-7 SUBTOTAL checks restored; Tract 9 header C6→75.34 / D6→"Tract 9", Tract 10 D6→"Tract 10"; Tract 2 two instrument-conservation VERIFY suspense rows (AT128, CN129), both columns net zero.
- **WI 1:** wellbore chain extended through Wellbore Assignment 2026-002547 Bk 2698/0069 (Martin's Empire → Stride Bank TTEE, 5/4/2026); Stride Bank current-holder row; Yale Oil dual assignment; col-C wellbore TBDs → "N/A - wellbore WI (no NMA)".
- **WI 2:** Silver Oak top-lease package OGL 64–69 documented (instruments/Bk-Pg verified against register); col-C WI/NRI TBDs resolved to "1.00 WI / 0.8125 NRI insofar as lessor's interest".
- **Well 1:** OCC-sourced bottom-hole/spacing/allocation reasoning; Spud/Perf/TD-TVD flagged with the exact missing document (scanned Form 1002A) not estimated; surface-call and operator discrepancy notes retained in-cell.
- **PLAT:** corrected schematic tract labels (matches legals; T6/T8 as west-side M&B strips; Lots 1–4 west side; "NOT A SURVEY").

**Rejected prior-pass (byfable) material after verification:** Tract 3 owner-row splits (90 cells — multiline names split on line breaks with interests divided among fragments, e.g. "White Birch, L.P." → two owners; kept examiner's originals); Tract 3/4/10 col-F deletions (125 cells; unsourced); byfable's B151 note (replaced).

## 5. Instrument-exclusion compliance
No mortgage/lien/UCC/ROW/easement/ORRI-only/surface-only instrument appears as a row/owner on Runsheet, any Tract sheet, or Title. rawdata retains all such records for awareness. Verified by type-scan of every Tract/WI instrument-column header and every Runsheet doc-type cell.

## 6. Open items intentionally left visible (no fabrication)
- Root-of-title +1.0 patent credits on each tract's first instrument column (sovereign not debited) and the genuine Tract 2 col-AE 0.001263 open balance — left visible, not force-balanced.
- HBP: OTC production unreachable; base-lease HBP left "Verify base HBP"; Well 1 shows Last Production 3/1/2026 (OCC status AC).
- Wellbore WI/NRI %: assignment exhibits not of record in the files; stated N/A/open with the exact document named.

## 7. Validation results (two consecutive clean passes)
- 19 sheets, names (incl. trailing-space `Title `), order, visibility, merged ranges identical to original; only worksheet/styles/workbook XML changed inside the package; all images/SVG/VML/comments byte-identical; no comments added.
- Zero `TBD` strings; every remaining VERIFY maps to a named missing document.
- Title OGL references numeric-only, all in register 1–69, no Bk/Pg lease citations, no legacy 109–114.
- Ten tracts foot to gross and tie to **637.42**; Title totals agree with tract grids; no negative acres.
- Zero cached formula errors; `fullCalcOnLoad` set.
- Highlights: OGL P1:V1 + 29 documented source-in gaps resolved & de-highlighted; **67** genuinely-unresolved gap highlights preserved, each with the exact missing document identified.
- 40-cell read-back verified against intent.

## 8. Environment limitations disclosed (unchanged since pass 1; re-tested this pass)
The session egress policy hard-blocks non-allowlisted hosts. Re-tested 7/3/2026 with the okcountyrecords API key from project notes: `okcountyrecords.com:443`, `public.occ.ok.gov`, OTC, and Google Drive binary endpoints all return proxy 403 (org policy — the proxy README directs reporting, not routing around, and a browser would traverse the same policy). `WebFetch` is egress-blocked (403 even on public pages); `WebSearch` returns only snippets that do not carry the specific well/instrument facts. Consequences: (a) no post-06/05/2026 recent-filing gap sweep — last verified entry remains 2026-003315, Bk 2704/142; (b) the 67 preserved gaps' underlying pre-2000/probate instruments could not be pulled to resolve them; (c) Well 1 Spud/Perf/TD-TVD remain flagged (Form 1002A not retrievable); (d) the FINAL .xlsx binary could not be written into Drive via the available text-payload upload channel — it is attached in chat and committed to git; drop the attached file into the Drive folder to complete the Drive copy. **What this deeper pass added despite the blocks:** full local OCR of the 88-page index, a 519-instrument parsed database, and 29 documented gap resolutions grounded in that database + the workbook's own Runsheet — no external host required.

---

**Cursory cleanup only from available workbook, county index (OCR), OCC, and OTC evidence. Not a certified title opinion. Open and verify items remain only where source evidence was insufficient.**
