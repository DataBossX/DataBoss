# P11 LEDGER — CANNOT BE CORRECTED FROM ITSELF

`RECEIPT_UTC = 2026-09-14T15:50Z`
`MODE = READ-ONLY · WRITES = 0 · WRITER_COUNT = 0`

I built the Book/Page cross-key corrector (`penterra/tools/crosskey.py`) to mechanise the
fix for the measured 15–19% doc-number error rate. Before recommending it be run, I checked
whether it *can* be run against the live ledger. **It cannot**, and the reason is structural.

## The ledger lacks the fields needed to check itself

| Measure | Count | Share |
|---|---:|---:|
| Ledger rows | 437 | — |
| Rows carrying a **Book/Page** | **17** | **3.9%** |
| Rows with the document number as **sole** identifier | **420** | **96.1%** |

Every one of the 17 Book/Page-bearing rows is also one of the 17 `MATCHED_IN_REPORT` rows.
The Book/Page was populated *from the workbook it matched*, not captured from the tract-index
face. On the other 420 rows the `BookPage`, `Date` and `Parties` columns are empty on most
pages — those rows are `vision_enumerated_docnos`, a bare list of numbers.

## Consequence

The one field that is **15–19% wrong** is, on 96% of rows, the **only** field present.
There is nothing to cross-check it against.

`crosskey.suggest()` requires corroboration by design — proximity alone never proposes a
correction — so on those 420 rows it correctly returns `NO_ORACLE_MATCH` and proposes
nothing. That is the tool behaving properly, not failing. A tool that *did* return
corrections there would be guessing, which is exactly the failure this whole exercise exists
to prevent.

## Scale of the problem

| At the measured rate | Rows misidentified (of 437) | Of those, uncheckable from the ledger alone |
|---|---:|---:|
| 15% (page 10) | ~66 | ~63 |
| 19% (page 4) | ~83 | ~80 |

So roughly **63–80 misidentified rows cannot be detected, let alone corrected, without
returning to the page renders.**

## What this changes

The corrective pass is **not** a data-cleaning job over the existing ledger. It is a
**re-extraction** from the 14 page renders, and it must capture, per row:

1. Document number
2. **Book/Page** — the unique locator; decisive in all 14 cases I face-proved
3. **Recorded date** and document date
4. Grantor / grantee

The renders carry all of this — I read Book/Page, both dates and both parties straight off
`p04.png` and `p10.png`. The information was available and was not captured.

Once a re-extraction has those fields, `crosskey.audit()` will check the whole corpus
deterministically against the Section 13 workbook oracle and emit ranked, evidence-cited
corrections. The tool is ready and tested; it is waiting on input it can actually use.

## Standing position, unchanged

- **Do not work the 136-row `ACCEPTED_INSERTION_REQUIRED` queue.**
- **Do not act on `JUSTIFIED_EXCLUSION` decisions** — a wrong number there loses a real
  instrument silently rather than duplicating one.
- **437** remains the correct denominator; row *counts* are sound, row *identities* are not.

Nothing was written. No ledger, workbook or package was modified.
