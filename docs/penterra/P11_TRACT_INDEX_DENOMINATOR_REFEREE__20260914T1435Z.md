# P11 TRACT-INDEX DENOMINATOR — INDEPENDENT REFEREE

`RECEIPT_UTC = 2026-09-14T14:35Z`
`MODE = READ-ONLY REFEREE · WORKBOOK_WRITES = 0 · DRIVE_WRITES = 0 · WRITER_COUNT = 0`
`I am not the P11 writer. No ledger, workbook or package was modified.`

## Headline

**The controlling tract-index denominator of 461 is superseded by a source-pixel
measurement of 437.** Under the stated precedence — `SOURCE PIXELS > newest exact-target
receipt > deterministic/native QA > model` — the newer Vision census governs, and **every
Section 11 completeness percentage computed against 461 is now wrong**.

This is not my measurement. The PC writer produced it at 14:09Z; I am refereeing it against
the 13:27Z reconciliation audit and confirming the arithmetic.

## Why 461 was never a measurement

`461` was **derived**, not observed: `473 raw − 12 implied overlap`, where `473 = 446 + 27`
and the 12 overlaps were **inferred by subtraction and never named**. The 13:27Z audit
itself labelled that row `INFERRED` and flagged "row-level overlap list is not attached".

`437` **is** a measurement: Vision row census over the controlling PDF
`11-45N-76W Campbell County, WY.pdf`, SHA-256
`31804cb0812275a78fec7f6271f008e71781da459f774bcc48e13b1503802e8f`, 11,041,017 bytes,
14 pages, **no text layer**. Header independently confirmed by Vision+OCR as
**SECTION 11 / TOWNSHIP 45 / RANGE 76 / CAMPBELL COUNTY, WYOMING** (an earlier "T43"
claim is recorded as falsified).

## Per-page reconciliation of the two censuses

| Page | 13:27Z audit | 14:09Z Vision (authority) | Delta |
|---|---:|---:|---:|
| p01 | 45 | 45 | 0 |
| p02 | 44 | 41 | **−3** |
| p03 | 42 | 43 | +1 |
| p04 | 44 | 43 | −1 |
| p05 | 44 | 42 | **−2** |
| p06 | 42 | 40 | **−2** |
| p07 | 41 | 41 | 0 |
| p08 | 40 | 39 | −1 |
| p09 | 42 | 43 | +1 |
| p10 | 41 | 40 | −1 |
| p11 | 21 | 20 | −1 |
| **Total** | **446** | **437** | **−9** |

Handwritten delta is **−9**. The `−24` quoted in the t194 census is the delta against the
**461 owner-order target**, not against 446. Both statements are true of different
baselines and must not be conflated.

Tyler supplement is **27** (p12=9, p13=11, p14=7) and is correctly held **separate** from
the handwritten denominator, not mixed into it.

## The overlap count collapses — and may explain the 3 unpartitioned entries

| Basis | Raw rows | Unique target | Implied overlap |
|---|---:|---:|---:|
| Old (446 handwritten) | 473 | 461 | **12** |
| New (437 handwritten) | 464 | 461 | **3** |

On the measured count, only **3** overlaps are implied, not 12.

**Hypothesis worth testing, explicitly NOT asserted:** the long-unexplained
`461 − 57 − 401 = 3` unpartitioned entries and these 3 implied overlaps may be the same
three records, in which case the "12 overlaps" never existed and both open items close
together. This must be **proved from the 461-key ledger row by row**, never adopted because
the numbers happen to agree.

## Classification closure — both t194 sets are internally sound

| Class | census `.md` | SCRUBBED `.json` |
|---|---:|---:|
| MATCHED_IN_REPORT | 17 | **37** |
| ACCEPTED_INSERTION_REQUIRED | 136 | 136 |
| JUSTIFIED_EXCLUSION | 54 | 54 |
| SOURCE_UNREADABLE | 189 | **169** |
| TRUE_HOLD | 41 | 41 |
| DUPLICATE_INDEX_ENTRY / SOURCE_MISSING / OUT_OF_SCOPE | 0 | 0 |
| **Sum** | **437** ✓ | **437** ✓ |

Both close exactly on 437. The scrub moved **+20 MATCHED_IN_REPORT / −20 SOURCE_UNREADABLE**,
net zero — a legitimate refinement, not drift. `SOURCE_MISSING = 0` is a strong result: every
index entry has custody.

**Oil/gas priority gate: PASS.** `ACCEPTED_INSERTION_REQUIRED` with `oilgas=True` is **136**,
against the ≥93 target. The scrub splits it 80 true / 56 false-scrubbed, total unchanged at 136.

## DEFECT RAISED — three irreconcilable workbook row totals

| Source | County workbook rows |
|---|---:|
| t194 census `.md` (preimage `383689f9…`) | **61** (17 matched + 44 unbound) |
| t194 SCRUBBED `.json` | **56** (37 matched + 19 unmatched) |
| 13:27Z reconciliation audit (R5) | **62** |

Three different denominators for the same workbook are in play. Until one is proved from
the workbook itself, **no matched-coverage rate is certifiable** — the numerator moved
(17 → 37) and the denominator moved (61 / 56 / 62) in the same hour.

## What this changes for the release gate

1. **Restate the denominator as 437** (handwritten, Vision-measured) with Tyler's 27 held
   separately, and retire 461 wherever it is quoted as controlling — including in the
   standing mandate.
2. **Recompute every completeness rate.** The previously "defensible" 57/461 = 12.36% is
   built on a superseded denominator and on a matched count that has since moved to 37.
3. **Name the 3 implied overlaps** from the ledger and test them against the 3 unpartitioned
   entries.
4. **Resolve 61 vs 56 vs 62** before any coverage figure is published.
5. **189 → 169 SOURCE_UNREADABLE** remains the dominant blocker: these are pages in custody
   that Vision has not yet read deeply enough. They are `UNREADABLE`, **not** `SOURCE_MISSING`,
   and must not be filled by inference.

Nothing here was written to a production target, and no value was invented. The 437 figure
is adopted as authority only because it is a direct measurement of a named, hashed source.
