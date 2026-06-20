# FINAL QA SCORECARD — 2026-06-19

**Overall: 88 / 100 — CONDITIONAL PASS** (target was 95; not reached because the
title conclusions themselves are gated on records that could not be pulled in
this environment — per the critical-truth rule, those gaps are reported, not
papered over).

| Criterion | Weight | Score | Notes |
|---|---:|---:|---|
| Tract chain completeness | 25 | 18 | All 8 tracts + unassigned QQ have anchors; full per-instrument chain preserved in Runsheet/OGLs but per-row tract tagging not completed. |
| Source citation strength | 20 | 18 | Every conclusion tied to a source ID; estimates labeled; SHA256 on master workbook. |
| Owner NMA reconciliation | 15 | 13 | Per-tract NMA reconciles to gross (±rounding); Tract 5 acreage open; unknowns kept in a bucket (not force-balanced). |
| Lease / HBP support | 15 | 13 | Verified Silver Oak expirations; HBP correctly held OPEN; blanket-HBP overstatement corrected. |
| Curative gap actionability | 10 | 10 | 12 prioritized gaps with exact search params + where to search. |
| Hyperlink / file integrity | 5 | 4 | Internal formulas verified; external portals logged as blocked. |
| Excel usability / formatting | 5 | 5 | Frozen headers, filters, wrap, widths, color-flagged warnings, SUM formula. |
| Local app & packaging | 5 | 2 | App/zip/desktop shortcut not built — remote Linux container, delivery is to Google Drive per user choice. |

## Must-pass checks
- [x] Final workbook opens without corruption (reopened via openpyxl).
- [x] No unexplained formula errors (0 error literals across 16 sheets).
- [x] All generated schema sheets exist (9) + 7 preserved source sheets.
- [x] Every tract has a chain anchor or a clear reason it is incomplete.
- [x] Every owner NMA estimate has source/evidence/confidence/curative.
- [x] Every lease status has support or is marked unknown/open gap.
- [x] Links tested and logged (LINK_QA).
- [x] README / executive summary exist.
- [~] All deliverables inside one folder — delivered to a single Google Drive folder (no local D:\ in this environment).

## Honest limitations
- NMA for all tracts except Tract 6 are **estimates**, not record title.
- **HBP is unconfirmed** — do not represent the section as held by production.
- **No new public research** was performed (portals blocked); chats/email were
  **not** found as exports (Gmail not enabled, no chat-export files present).
- App, .bat launchers, desktop shortcut, and local zip from the prompt are
  **not applicable** to this remote Linux container and were not built.
