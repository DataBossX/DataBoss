# TitlePreviewFixer 3-Row Preflight — 20260618_034219

> MOCK OCR — synthetic, offline, zero-cost. Not a real county extraction.

## Gate status

| Gate | Status |
|------|--------|
| 1 Workbook inspect | ✅ ran |
| 2 Review copy | ✅ ran |
| 3 Link export | ✅ ran |
| 4 Manual browser login | ⏸️ DEFERRED (needs real site + .auth) |
| 5 Open one link | ⏸️ DEFERRED |
| 6 Click View | ⏸️ DEFERRED |
| 7 Screenshot in memory | ⏸️ DEFERRED |
| 8 OCR strict JSON | ✅ ran (MOCK) |
| 9 Compare row | ✅ ran |
| 10 Write suggestions | ✅ ran (copy only) |
| 11 3-row test | ✅ ran |
| 12 Human review | 👤 required next |
| 13 Batch mode | 🔒 requires explicit approval |

- Source: `/home/user/DataBoss/review_outputs/mock_runsheet_20260618_034219.xlsx`
- Review copy: `/home/user/DataBoss/review_outputs/mock_runsheet_20260618_034219_REVIEW_20260618_034219.xlsx`
- Source hash unchanged: **✅ yes**
- Cost guard: $0.0000 / $1.00 (within)
- Inspection report: `workbook_inspection_20260618_034219.md` · Links: `workbook_links_20260618_034219.csv` · Cost: `cost_guard_20260618_034219.md`

## Per-row outcomes

| Row | Status | Confidence | OCR valid | Mismatches | Reason |
|-----|--------|-----------|-----------|-----------|--------|
| 0 | Auto-Suggested | 0.93 | ✅ | - | confidence above threshold, no uncertain fields |
| 1 | Needs Human Review | 0.40 | ✅ | - | confidence 0.40 < 0.85 |
| 2 | Auto-Suggested | 0.93 | ✅ | Book: wb='1102' ocr='9999' | confidence above threshold, no uncertain fields |

## Failure buckets

- **comparison**:
  - row 2: Book(1102!=9999)

## Verdict

Preflight ran in gates against MOCK data. Row 2 was correctly held for **Needs Human Review** (low confidence) and Row 3's **Book mismatch** was caught by row-compare — not auto-applied. Source workbook untouched.

**Do NOT enable batch mode (Gate 13) until:** keys rotated, real `.auth` captured, real OCR provider wired behind the cost guard, and a human approves the 3-row results.

## Raw outcomes (JSON)

```json
[
  {
    "row_index": 0,
    "status": "Auto-Suggested",
    "confidence": 0.93,
    "reason": "confidence above threshold, no uncertain fields",
    "mismatches": [],
    "ocr_valid": true
  },
  {
    "row_index": 1,
    "status": "Needs Human Review",
    "confidence": 0.4,
    "reason": "confidence 0.40 < 0.85",
    "mismatches": [],
    "ocr_valid": true
  },
  {
    "row_index": 2,
    "status": "Auto-Suggested",
    "confidence": 0.93,
    "reason": "confidence above threshold, no uncertain fields",
    "mismatches": [
      "Book: wb='1102' ocr='9999'"
    ],
    "ocr_valid": true
  }
]
```
