# P11 LEDGER DOC-NUMBER ERROR RATE — SYSTEMIC, NOT A PAGE-10 ANOMALY

`RECEIPT_UTC = 2026-09-14T15:35Z`
`MODE = READ-ONLY · WRITES = 0 · WRITER_COUNT = 0`

Question under test: **was the 15% doc-number error rate on page 10 representative, or was
page 10 unusually bad?** It decides whether the whole ledger needs re-reading or just one page.

Second page read: **`p04.png`**, Drive `1kx_KKZfHnH_EjCWxTZyRpMwjVk-6NWhO` (5,451,450 B).
Page 4 is `vision_enumerated_docnos` at confidence **0.88** — the same high-confidence class.

## Answer: SYSTEMIC. Page 4 is worse than page 10.

| Page | Enumerated rows | Confirmed/probable misreads | Rate |
|---|---:|---:|---:|
| p10 | 40 | 6 | **15%** |
| p04 | 43 | 8 | **19%** |

## Page 4 misreads

### Certain — face + independent workbook corroboration

**A three-in-a-row failure on the Unit Agreement amendments.** The face reads
`Ist Amend … Cities Service Co.` / `2nd Amend … The Public` / `3rd Ague Cities Service Co.
The Public`, recorded `Aug 12 1981` at `Photo 288 / 292 / 298`.

| Ledger | True | Corroboration |
|---|---|---|
| `500171` | **`500112`** | S13 wkbk: First Amendment of Unit Agreement, Cities Service Co. → The Public, dtd 3/27/1981, rec 8/12/1981 |
| `500172` | **`500113`** | S13 wkbk: Second Amendment, dtd 3/27/1981, rec 8/12/1981 |
| `501189` | **`500114`** | S13 wkbk: Third Amendment, dtd 5/14/1981, rec 8/12/1981 |

**The two Christensen warranty deeds.** Face reads `5:22831 W.D. Charles M. Christensen →
Janet Kay` (`Dec 31 1982, Photo 561, dtd Dec 27 1982`) and `5:22832 … → Robert Frederick
Christensen` (`Photo 568`).

| Ledger | True | Corroboration |
|---|---|---|
| `521831` | **`522831`** | S13 wkbk `0654-0561`, Warranty Deed → Janet Kay Christensen, 12/27/1982 → 12/31/1982 |
| `521832` | **`522832`** | S13 wkbk `0654-0568`, Warranty Deed → Robert Frederick Christensen |

### Strong

| Ledger | True | Corroboration |
|---|---|---|
| `545500` | **`548300`** | S13 wkbk `0754-0001`, Release of Lien, 5/15/1984 → 6/13/1984; face shows those dates |
| `545501` | **`548301`** | S13 wkbk `0754-0004`, Mortgage and Security Agreement, same dates |
| `509461` | **`507688`** | S13 wkbk `0597-0020`, Mortgage, Western Gas Processors → Republic Bank Dallas, 2/1/1982 → 2/17/1982; face shows "Feb 17 1982". `507688` is **absent** from the ledger and `509461` is spurious |

### Correct on page 4

`492814`, `497899`, `501614`, `504298`, `504300`, `504301`, `520371`, `523059`, `523060`,
`524188`, `531955`, `536366`, `541967`, `542550`, `545405`, `551615`, `553340`, `553558`,
`560554`. The ledger is right more often than wrong — which is exactly why sampling cannot
substitute for a complete re-read.

## Why the errors cluster the way they do

Every confirmed misread is a **digit substitution inside a run of near-identical numbers**
(`500112/113/114`, `522831/832`, `548300/301`). Sequential county filings differ by one or
two digits, so a single misread digit silently produces a *plausible* neighbouring document
number rather than an obvious error. That is the worst failure mode for a stable key: it
does not look wrong, and it will not trip any structural check — my own `stable_key.py`
parses `500171` perfectly happily.

## Corroboration method that works

**The Section 13 county workbook is an effective oracle.** Many Campbell instruments touch
several sections, so its 332 verified rows (332 unique keys, 0 duplicates, confirmed earlier
today) carry Book/Page for a large share of the Section 11 tract-index population. In all
14 cases across both pages, **Book/Page plus recorded date settled the identity where the
doc number alone did not.** That is the cross-key to use.

## Standing recommendation — reinforced

1. **Do not work the 136-row `ACCEPTED_INSERTION_REQUIRED` queue.** At 15–19%, **20–26** of
   those rows are misidentified; some are already in the workbook and would be duplicated.
2. **Do not trust `JUSTIFIED_EXCLUSION` either.** Three of page 10's six errors were
   exclusions — a wrong number there loses a real instrument silently.
3. **Re-read all 11 handwritten pages against the renders** (`p01`–`p11` in Drive folder
   `1WDxiC6k-5FBz5_G6gW45aa344v6OQEb8`), keyed on **Book/Page + recorded date**, not doc number.
4. **Recalibrate confidence.** Pages marked `0.88`–`0.90` measured 81–85% accurate on doc
   numbers. The confidence figures currently overstate reliability by roughly 5–9 points.
5. The **437** denominator is unaffected — row *counts* are sound; it is row *identities*
   that are not.

Two pages of eleven have been checked. The remaining nine are unmeasured, and the rate on
them should be assumed to be in the same 15–19% band until shown otherwise.

Nothing was written. No corrected value was inserted into any ledger, workbook or package.
