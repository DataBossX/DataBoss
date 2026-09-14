# P11 TRACT-INDEX LEDGER — INDEPENDENT REFEREE (t194)

`RECEIPT_UTC = 2026-09-14T15:05Z`
`MODE = READ-ONLY REFEREE · WORKBOOK_WRITES = 0 · LEDGER_WRITES = 0 · WRITER_COUNT = 0`

Artifact refereed: `P11_TRACT_INDEX_LEDGER__t194.csv`
(Drive `1SchwYz59Nx6SuA0JoDJOm4IMl8lrxIX7`, 37,519 B, 13:54:05Z)

## PASS — ledger structure is sound

| Check | Result |
|---|---|
| Ledger data rows | **437** |
| Per-page counts vs t194 census (45,41,43,43,42,40,41,39,43,40,20) | **identical** |
| Row-slot accounting | every page enumerates 1..n with no gaps |

The ledger is an honest artifact: unread rows are carried as explicit
`SOURCE_UNREADABLE` row slots with confidence 0.50–0.55 rather than dropped or
back-filled. That is the correct handling and it is why the count closes.

## FINDING 1 — this is a 437-key handwritten ledger, not a 461-key ledger

The ledger covers **handwritten pages p01–p11 only**. The 27 Tyler modern entries
(pp. 12–14) are **not in it**. Release blocker #1 asks for a ledger over the full unique
universe; what exists covers `437` of `437 + 27 = 464` raw rows.

Consequence: **no workbook row whose identity is a modern Tyler filing can ever match this
ledger.** Rows such as `2023-00118`, `2026-02650`, `2025-07237`, `2024-06326`, `2025-01188`,
`2023-03592`, `2023-06492`, `2023-07941`, `2025-08368`, `2026-00341` are in the workbook and
structurally unmatchable here. Part of the apparent match shortfall is this scope gap, not
a real omission.

## FINDING 2 — the SCRUBBED totals contradict the ledger

| Source | MATCHED_IN_REPORT |
|---|---:|
| Ledger (counted: rows carrying `match_workbook_row`) | **17** |
| t194 census `.md` | 17 — **agrees** |
| t194 SCRUBBED `.json` | 37 — **disagrees** |

The scrub claimed `+20 MATCHED_IN_REPORT / −20 SOURCE_UNREADABLE`. I previously accepted
that as internally consistent because it nets to zero and still sums to 437. **It is not
reflected in the ledger.** Either the scrub was applied to a ledger revision not published,
or the 37 is unsupported. Until reconciled, **17 is the only match count with a row-level
basis**, and any coverage rate built on 37 is unsupported.

## FINDING 3 — the workbook join is stale by 7 rows

The highest `match_workbook_row` referenced is **61**. The live county workbook
(`QA_HOLD_R5.xlsx`, 13:21:04Z) that I measured has **68** rows. The ledger was joined
against a 61-row workbook (preimage `383689f9…`) and has not been re-joined since the three
staged insertions and the other new rows landed. **All 17 match pointers must be re-verified
against the 68-row workbook before any coverage figure is published** — row indices shift.

## FINDING 4 — an OCR misread creates a phantom omission and hides a real match

Ledger `p10r17` reads:

```
1007025 | OGL | "Judy Lea Wickersham" | ACCEPTED_INSERTION_REQUIRED (i.e. missing from report)
```

The county workbook carries, and **I face-proved earlier in this session**:

```
1007085 | 2929-0210 | Assignment of Oil and Gas Leases
         | "Judy Lea Wickam, formerly Judy L. Jones" -> Wickam Minerals LLC
         | 1.00% ORRI, Lease Serial W 47318, Book 2929 of PHOTOS Page 00210
```

`1007025` vs `1007085`, `Wickersham` vs `Wickam`. These are the same instrument. The effect
is doubly wrong: it **manufactures an omission that does not exist**, and it **suppresses a
genuine match**. Because `ACCEPTED_INSERTION_REQUIRED` is the work queue, this row would be
re-abstracted into a workbook that already contains it — creating a duplicate.

**This must be corrected from the face before the 136-item insertion queue is worked.**

## FINDING 5 — party/type drift on rows already declared MATCHED

| Ledger | Workbook | Drift |
|---|---|---|
| `437884` — "Rel", **John J. Wold** | "Assignment of Uranium Mining Lease", **John S. Wold** | instrument type **and** middle initial |
| `999340` — "Memo", **Deluxe Energy Prod Co** | "Corrected Memorandum…", **Devon Energy Production Company** | party name |

Both are classified `MATCHED_IN_REPORT`. A match asserted on a doc number while the type and
parties disagree is not a verified match. Given Finding 4, **the doc numbers themselves are
not reliable enough to carry a match alone** — each of the 17 needs face confirmation.

## FINDING 6 — document-number ordering breaks between p09 and p10

`p09` ends at `964251`; `p10` begins at `958045`. Doc numbers ascend within every other page
transition. This is either a page-order error, a misread, or a legitimate tract-grouped
(not chronological) index. It must be resolved before the ledger is used to prove coverage,
because ordering is the main defence against a skipped or duplicated page.

## Revised blocker list for P11

1. **Extend the ledger to the 27 Tyler entries** — it is currently 437 of 464.
2. **Reconcile 17 vs 37 MATCHED_IN_REPORT.** Only 17 has a row-level basis.
3. **Re-join against the 68-row workbook**; all 17 pointers are stale.
4. **Fix `1007025` → `1007085` from the face** before working the insertion queue, or a
   known instrument will be abstracted twice.
5. **Face-confirm all 17 matches** — doc-number-only matching is demonstrably unsafe here.
6. **Resolve the p09/p10 ordering break.**
7. Denominator remains **437 measured**, not 461 (see the 14:35Z referee).

No ledger, workbook or package was modified. Nothing was filled, and no value was invented.
