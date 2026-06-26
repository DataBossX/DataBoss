# CHANGELOG_CLAUDE.md — Final Claude Review Pass

Roger Mills 31‑12N‑24W · 2026‑06‑26 · source → `outputs/03_CLAUDE_VERIFIED.xlsx`

## Changes applied to the workbook binary
1. **Removed 2 orphaned/stale external links** ("Fix links").
   - `…/Users/emorris/Downloads/OR 34-28N-08W  Grant Co.  (blm 1-13-2012).xls`
   - `…/Users/emorris/Downloads/OR 13-05N-08ECM Cimarron Co OK (Texhoma Pros)…(2b).xls`
   - Both were template-inherited references to **unrelated projects/counties**,
     used by **zero formulas** in this workbook (verified: 0 formulas contain
     external `[..]` references). Removed `xl/externalLinks/*`, their rels, the
     `<externalReferences>` element in `workbook.xml`, the relationships in
     `workbook.xml.rels`, and the `[Content_Types].xml` overrides.
   - Edit performed at the XML level (not via openpyxl) specifically to avoid
     dropping embedded media/comments.

## Explicitly NOT changed (hard constraints honored)
- **Tabs:** 20 tabs, same names, same order. None added/deleted/renamed/reordered.
- **Formatting:** preserved exactly. Verified after rebuild: 2 embedded images
  (`image1.png`, `image2.jpeg`), 11 comment sets, 15 drawing parts, all merged
  cells and formulas intact.
- **Colors:** none added. (No yellow critical-document highlights were applied in
  this pass — see Deferred below.)
- **Facts:** none invented. No net acres, dates, royalties, or ownership added.
- **Final all-three-verified report:** not touched.

## Deferred edits (documented, not applied to binary — with reason)
These were requested but are **deferred to protect the embedded plat image and
cell comments**, which programmatic spreadsheet editors (openpyxl/pandas) drop on
save. Apply them in Excel/LibreOffice, where formatting is preserved, or via
further surgical XML edits in a follow-up.

1. **Condense AI-looking notes.** Inspected the 8,880 shared strings: the verbose
   notes are **fact-specific** (each carries distinct Book/Page, dates, parties,
   fractions) — there is **no high-frequency pure-boilerplate string** safe to
   bulk-replace. Condensing them safely is a manual, per-note edit; doing it
   programmatically risked dropping specific title facts, which the rules forbid.
   Deferred rather than risk fact loss.
2. **Merge Tract 4 duplicate document columns** (`2251/0529`, `2406/0228`).
   Merging shifts the balanced chain grid and its net-acre allocation formulas;
   recommended as a verified manual merge in Excel after confirming the two
   columns are the same instrument. See `GAP_LIST_CLAUDE.md` #7.
3. **Yellow critical-document highlights.** Apply in Excel to the critical
   instruments (e.g., the six 2026 Silver Oak top leases, the Lalexander 1‑31
   wellbore ORRI 2698/0069, the prior 2004-era base leases) so the highlight
   fills survive without disturbing other formatting.

## Companion artifacts produced
- `outputs/03_CLAUDE_VERIFIED.xlsx` — verified candidate (changes above)
- `QA_LOG_CLAUDE.md` — checks run and results
- `GAP_LIST_CLAUDE.md` — Open / Needs Verification items
- `SOURCE_MAP_CLAUDE.csv` — 1,470 documents: Book/Page → type → parties → source file
- `COST_LOG_CLAUDE.csv` — run/cost log
- repo `CLAUDE.md` — standing reviewer rules
