# Aggregate Findings (Public / Non-Reversible Metrics)
## Master Evidence Verification — Section 32, T11N-R25W, Beckham County, OK

Aggregate counts only. No party names, addresses, book/pages, hashes, or file IDs. Full detail is in the Internal package.

---

## Instrument register (run sheet)

| Metric | Value |
| --- | ---: |
| Instrument rows reviewed | 144 |
| `LIKELY MATCH` (image-backed / countywide) | 35 |
| `PARTIAL MATCH` (metadata / index only) | 109 |
| `VERIFIED` | 0 *(authorities 1–4 unreachable)* |

Evidence-class breakdown (144 rows): image-backed identity path 2; direct image pixel-verified 29; countywide screen 4; public metadata + local index 31; county API metadata only 49; local index only 29.

## Index reconciliation

| Metric | Value |
| --- | ---: |
| Index entries transcribed | 1,981 |
| Source images inventoried (prior work) | ~4,893 |
| Exact index ↔ image matches (unique instrument no. or book/page) | 32 |
| Image without index entry | 4,863 |
| Index entry without image | 1,936 |
| Multiple possible matches | 13 |
| Index entries at `INDEPENDENT_REVIEW_PENDING` | 1,981 (all) |

Index defects: one stamped index page confirmed **missing**; one stamped page **duplicated** (multiple physical occurrences). Duplicate/out-of-order index conditions tracked and flagged; none double-counted.

## Spreadsheet QA (three workbooks)

| Workbook role | Live formulas | Hidden working sheets | Verdict |
| --- | ---: | --- | --- |
| Selected primary | 5,126 | 2 hidden (correct) | **Selected — correct** |
| Prior-lineage sibling | 5,126 | 2 hidden | consistent |
| Rejected candidate | 4,838 | none (all visible) | **Rejected — correct** |

- No formula errors (`#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, `#NAME?`) detected in any workbook.
- No hyperlinks present (none to break).
- "Duplicate rows" flag on the title sheet reviewed and cleared — structural repeated total/header rows, not data duplication.
- Tract acreage sums to the stated section total (arithmetic/geometry consistent); not confirmed against recorded legals (authorities unreachable).
- Cross-format integrity: **PASS**.

## Substantive title conclusions — status

| Conclusion | Status |
| --- | --- |
| Party-of-interest identity on the subject lease (identity path) | Supported by two image-backed confirmatory conveyances; not county-re-verified |
| Party-of-interest exact WI / NRI / ORRI / net acres | **NOT established** — do not state a number |
| Present fee-mineral ownership (all tracts) | **NOT established** — no complete post-patent chains |
| Base oil-and-gas lease | **NOT established** — not in evidence |
| Section-wide HBP | **NOT established** — well/regulatory presence ≠ HBP proof |

Prior-run rejections upheld: the ~48.75% figure is a **different** party's interest and must not be attributed to the party of interest; a key index-only book/page lead is **not** recorded-instrument proof.

## Open-item severity profile (15 items)

- **CRITICAL:** base lease missing; the operative vesting branch missing; exact quantum not determinable; a key legal-description conflict; present fee-mineral ownership not established.
- **HIGH:** three sovereign-inception patents missing; a bridge assignment lacks a subject schedule line; two wellbore/ORRI chains unresolved; a wellbore-carve lease-ID mismatch; a bridge-instrument page conflict; a missing index page.
- **MEDIUM:** a duplicated index page; run-sheet template capacity vs. full support inventory.

## Release recommendation

**HOLD — NO RELEASE** as a quantified ownership or present-title conclusion. The package may be delivered as clearly-labeled **cursory / internal-review draft work product** accompanied by the open-items and curative list; it must not be presented as a title opinion, certified abstract, or a statement of ownership.

## Path to a releasable determination

Pull and abstract the certified images this environment could not reach (base lease; the vesting-branch instruments; the wellbore/ORRI chains; the conflicting legal-description instrument; the complete post-patent mineral chains for all five tracts), then re-verify every register row and index entry against OKCountyRecords.
