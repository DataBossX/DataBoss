# Section 27-11N-25W — Beckham County, OK — Diversified Cursory Title Research

Cursory leasehold (working-interest) review of Diversified's apparent interest in the
Section 27, 11N-25W, 640-ac pooled unit (OCC Order 429172). **Not a title opinion.**

## Contents
- `deliverables/` — final updated workbook (19 tabs) + research summary, gaps, QA, API/OCR log,
  instrument index, chain audit, download manifest, and the paid-download approval doc.
- `records_parsed/section27_index_parsed.csv` — structured transcription of the 27-page
  Beckham County Section 27 grantor index (visual read; H/M/L confidence per row).
- `scripts/` — repeatable pipeline (inspect → parse → build → QA).

## Key figures (apparent / cursory)
- Diversified apparent WI: **0.700520833** (448.333333/640)
- Residual / open: **0.299479167** (191.666667/640) → ties to 640 ac / 1.000000 WI
- NRI: **UNRESOLVED / ESTIMATE-ONLY**

## Important limitations
- Built with **no OKCountyRecords API access** (none available in this environment); no paid
  records were downloaded. The 2017–2026 corporate assignment chain (2266/194 etc.) is **not**
  in the provided county index and was **not** independently verified.
- The **leasehold/OGL/assignment/ORRI layer WAS verified** against the county grantor index.
- Raw record images (24MB index PDF, rendered PNGs) are intentionally **not** committed.
