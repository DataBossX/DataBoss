# P11 LEDGER DOC-NUMBER ACCURACY — FACE-PROVED ON TRACT-INDEX PAGE 10

`RECEIPT_UTC = 2026-09-14T15:20Z`
`MODE = READ-ONLY · WRITES = 0 · WRITER_COUNT = 0`

Source read: tract-index render **`p10.png`**, Drive `1L-aktfFzPsZOClAEosd3v9m0pndZdeIN`
(6,640,530 B, 220 dpi, from the controlling 14-page PDF SHA `31804cb0…`).

## Finding 4 is CONFIRMED from source pixels, not inference

The tract-index face reads, in the clear:

```
1007085   Judy dea Wickham   Wickam Minerals   Feb 23 2015   Photo 210   Nov 18 2014
```

The ledger (`p10r17`) records `1007025 / "Judy Lea Wickersham"` and classes it
`ACCEPTED_INSERTION_REQUIRED` — i.e. *missing from the report*.

Four independent sources agree the true identity is **`1007085`**:

| Source | Value |
|---|---|
| Tract-index face (`p10.png`) | `1007085` · Wickham → Wickam Minerals · Photo 210 · rec 2/23/2015 · dtd 11/18/2014 |
| Section 11 county workbook | `1007085 \| 2929-0210` · Judy Lea Wickam fka Judy L. Jones → Wickam Minerals LLC |
| Section 13 county workbook | `1007085 \| 2929-0210` |
| **The instrument itself**, face-read earlier this session | BLM Form 3000-3, Book 2929 of PHOTOS Page 00210, 1.00% ORRI, Lease Serial W 47318 |

**`1007025` does not exist.** The row is `MATCHED_IN_REPORT`, not an omission. Left in the
insertion queue, it would be abstracted into a workbook that already contains it.

## This is systemic, not a one-off: six doc-number misreads on one page

Reading the whole page-10 face against the ledger and corroborating each against a county
workbook that carries the same instrument with its Book/Page:

| Ledger | Face / corroborated true value | Corroboration | Ledger classification |
|---|---|---|---|
| `1007025` | **`1007085`** | face + S11 wkbk + S13 wkbk + instrument face (`2929-0210`) | AIR — **wrong, is matched** |
| `1008031` | **`1008002`** | S13 wkbk `2932-0565`; face shows "Photo 565", "Mar 11 2015" | JUSTIFIED_EXCLUSION — excluded on a number that does not exist |
| `1014856` | **`1014885`** | S13 wkbk `2973-0005`, Anadarko E&P Onshore → Moriah Powder River | AIR |
| `1014902` | **`1014891`** | face "WPX ENERGY ROCKY MTN → MORIAH POWDER RIVER"; S13 wkbk `2974-0022` | AIR |
| `1028821` | **`1028924`** | face "Surv. Charles M. Chris\[t\]ensen"; S13 wkbk `3061-0618` Affidavit of Survivorship | JUSTIFIED_EXCLUSION |
| `1028825` | **`1028925`** | face "QCD … J+R Christen\[s\]on Land, LLC"; S13 wkbk `3061-0624` Quit Claim Deed | JUSTIFIED_EXCLUSION |

**Six errors in 40 enumerated rows on a single page — a 15% doc-number error rate.**

Page 10 is one of the pages the census marks `vision_enumerated` at **confidence 0.90** —
i.e. one of the *high*-confidence pages. The stated confidence is not supported by the face.

## Finding 5 also confirmed

The face reads `999340  memo-  Devon Energy Prod. Co, LP, etal  /  The Public`.
The ledger records **"Deluxe Energy Prod Co"**. Confirmed misread on a row already declared
`MATCHED_IN_REPORT`.

## Rows that are correct

`1015362`, `1019813`, `1034500`, `1039878`, `1042393`, `1042394`, `991144`, `999340`
(number correct, party misread). The ledger is not uniformly wrong — which is precisely why
a spot check cannot substitute for a full re-read.

## Consequence — this invalidates the matching exercise, not just six rows

1. **Doc numbers cannot serve as stable keys at this accuracy.** The whole 437-row ledger is
   keyed on them, and `tools/stable_key.py` will faithfully produce a *wrong* key from a
   wrong number. Deterministic tooling cannot repair a bad read.
2. **The 136-row `ACCEPTED_INSERTION_REQUIRED` queue is unsafe to work.** At ~15%, roughly
   **20 of those 136** may already be in the workbook. Working the queue as-is would inject
   duplicates into the production index.
3. **`JUSTIFIED_EXCLUSION` decisions are unsafe too.** Three of the six errors are exclusions
   — instruments deliberately dropped on a doc number that does not exist. An exclusion is a
   *decision not to abstract*, so a wrong number there silently loses a real instrument.
4. **The 17 matches need re-verification**, since one confirmed match (`999340`) already
   carries a misread party.

## Required before any P11 insertion work

1. **Re-read every enumerated doc number against the page renders** — all 11 handwritten
   pages, not just page 10. `p01.png`–`p14.png` are on Drive in folder
   `1WDxiC6k-5FBz5_G6gW45aa344v6OQEb8`, so this is executable now.
2. **Cross-key every candidate against the Section 13 and Section 11 workbooks by Book/Page**,
   not by doc number. Book/Page proved decisive in all six cases here.
3. **Re-run the classification** after correction; the AIR/EXCLUSION/MATCHED split will move.
4. **Do not work the 136-item queue** until 1–3 are complete.
5. Recalibrate the confidence model: `0.90 / vision_enumerated` was 85% accurate on this page.

Nothing was written. No ledger, workbook or package was modified, and no corrected value was
inserted anywhere — these are findings for the P11 writer to apply under its own lease.
