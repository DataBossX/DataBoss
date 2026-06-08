# Section 27-11N-25W — Beckham County, OK — Diversified Cursory Report: Research Summary

**Prepared:** 2026-06-08  •  **Scope:** Cursory review of Diversified's *apparent leasehold (working) interest* in the Section 27, 11N-25W pooled unit (OCC Order 429172 / CD 980004527).
**This is a cursory report, NOT a title opinion. No title facts were invented.**

## Tract structure (verified, = 640.00 ac)
| Tract | Description | Gross ac |
|---|---|---|
| 1 | NE/4 | 160.00 |
| 2 | NW/4 | 160.00 |
| 3 | SE/4 | 160.00 |
| 4 | SW/4 less 1.00-ac church tract | 159.00 |
| 5 | 1.00-ac Buffalo Missionary Baptist Church tract (in SW/4) | 1.00 |
| **Total** | | **640.00** |

## Headline interest (carried, apparent)
- **Apparent Diversified-family WI:** 448.333333 net ac / 640 = **0.700520833**
- **Residual / open / non-Diversified / unverified:** 191.666667 net ac / 640 = **0.299479167**
- Section reconciles to **640.000000 ac** and **1.000000000 WI**.
- These are **apparent leased-coverage fractions, not proven working interests.** Per-lessor / per-tract net mineral acres are **not derivable from the index** in a cursory review.

## What was actually done in this environment
- **No OKCountyRecords.com API access** was available (no API key in env/config; outbound access is policy-restricted; the prompt's local `D:\` workspace does not exist in this Linux container). **No new records were purchased or downloaded.**
- The provided **27-page Beckham County Section 27 grantor index** (`11N_25W_27_Index.pdf`) was rendered to images and **read page-by-page** (visual OCR; tesseract is unreliable on these handwritten/grid ledgers).
- The two provided working workbooks (6/8/2026) were inspected, reconciled, and **consolidated** into one updated workbook (data-rich version + best report structure).

## Key verification result — the leasehold layer is corroborated
Every leasehold/OGL/assignment/ORRI book-and-page in the report's Runsheet/OGLs was **independently matched to the county grantor index**, including:
- **French Energy** base/top leases — 1432/20–68, 1433/213, 1435/159, 1580/79–115
- **Arrowhead Resources** — 1574/272–284 (→ Lortz 1576/302 → St. Mary 1577/102)
- **Todco Properties** — 1592/42–52, 1687/160–170, church 1588/245 (→ Kaiser-Francis)
- **Sanguine, Ltd.** controlling depth-limited HBP block — 1672/130–141 and **1717/456–509**
- **Assignment / consolidation chain** — French Energy→Sanguine 1504/11, 1597/427; partial 1505/31
- **ORRI burden stack** — Sanguine→Hauschild 1626/104; Kaiser-Francis→**GBK 3%** 1636/188; Sanguine→Vastar/Enogex/Palace 1638/150; Sanguine→Nelson group 1641/324–339; Leroy Royalty 1663/497

**Controlling depth:** Diversified's apparent interest is **depth-limited to deep rights below the stratigraphic equivalent of ~17,960'/17,860'** (TD+100 in the Mandrell #2-27, W/2 SE/4), per the Sanguine OGL depth clauses and the 1719/304 partial release. **Cherokee is NOT supported** by any provided record.

## What could NOT be verified here
- The **2017–2026 corporate assignment instruments** that carry the interest to Diversified (**2266/194, 2307/894, 2308/123, 2340/218, 2401/214, 2451/4, 2480/824**) are **not present in the provided county index** and could not be independently confirmed without OKCR API access. They are carried **as cited in the prior report** and flagged.
- **NRI / depth burdens:** **UNRESOLVED / ESTIMATE-ONLY.** The ORRI stack is unmetered and per-lessor NMA is unknown. The often-quoted `0.700520833 × 0.8125 = 0.569173177` is an **estimate only** (3/16 royalty, ORRIs ignored) — not a bookable NRI.

## Record counts
- Records searched/reviewed: **27 index ledger pages** (entire provided index) + 2 workbooks.
- Records OCR'd/read: **27 pages** rendered; key typed pages (leasehold layer) fully transcribed.
- Index entries parsed to structured data: **81** (see `Instrument Index` tab / `records_parsed/section27_index_parsed.csv`).
- Records downloaded (paid): **0** (none authorized/available; see download-approval doc).

## Confidence
- **Leasehold / OGL / depth layer: MEDIUM–HIGH** (independently verified vs county index).
- **Diversified WI quantum (0.700520833) & succession chain: LOW–MEDIUM** (apparent fraction; corporate chain not verifiable here).
- **NRI / per-tract NMA: LOW / UNRESOLVED.**
- **Overall: MEDIUM** for a cursory leasehold reconstruction; **not** acquisition/division-order grade.
