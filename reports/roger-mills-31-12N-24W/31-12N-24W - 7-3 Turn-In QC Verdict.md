# QC Verdict — Section 31-12N-24W turn-in files (as of 7-3-2026)

Independent TitleFinisher audit of the latest workbooks in the Drive folder.

## 31-12N-24W … (7-3-26) - NHE.xlsx  — the clean 19-sheet turn-in candidate
| Check | Result |
|---|---|
| 19-sheet structure (names/order) | PASS |
| Bare "TBD" cells | PASS — none |
| Formula error literals (#REF!/#VALUE!/…) | PASS — none |
| Source-in gap highlights | 17 remaining (down from 95 on the 7-1 base) |
| Excluded instruments on Runsheet | **FAIL — 2 rows**: 399 Memorandum of Option for Easement (Bk 1883/582); 440 Partial Release (Bk 2121/77) |

**Fix delivered:** `…(7-3-26) - NHE - CLEANED.xlsx` — the two excluded rows cleared (values only,
grid/format intact, rawdata retains them). Re-audit: **all checks PASS**, only 1 worksheet XML
changed, all media/comments/threaded-comments/external-links byte-identical.

## 31-12N-24W … BEST TURN IN COPY.xlsx  — working/audit master, not a clean turn-in
| Check | Result |
|---|---|
| Sheet count | 106 tabs (helper/audit/BAK/Cursor_* tabs) — not the 19-sheet deliverable |
| Bare "TBD" / formula errors | PASS |
| Tract net-acre footing | cached values missing (0.000 when read) — **needs an Excel open+recalc+save** so numbers display |
| Excluded instruments on Runsheet | same 2 rows (399, 440) present |

**Recommendation:** turn in the **CLEANED 19-sheet 7-3 NHE**. Keep the BEST TURN IN COPY as the
internal audit master. Before any turn-in, open the file in Excel once and save so all formula
values are cached.

## Remaining open (both files) — require recorded images, see the Ownership Report
17 source-in gap highlights on the 7-3 NHE; base-lease HBP (OTC/OCC); probate for the Dold and
Ella Pearl Kirk successions; WI assignment percentages; the disclosed open balances on Tracts
2/4/5/7/9. None are fabricated; each is itemized with the document to pull.
