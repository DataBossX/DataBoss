# Verification Methodology (Public / Generic Procedure)
## Master Evidence Verification — Section 32, T11N-R25W, Beckham County, OK

This document describes **how** the verification was performed. It contains no client party names, addresses, book/page citations, hashes, or file IDs, and is safe for the public repository. The evidentiary detail lives in the Internal package.

---

## 1. Authority order (per mandate)

1. Official OKCountyRecords → 2. Recorded images → 3. Recorded index → 4. Original county document images → 5. Project spreadsheets → 6. Prior AI reports.

**Environment reality:** authorities (1)–(4) were **not reachable** in this execution environment:
- **OKCountyRecords** returns HTTP 403 through the network proxy — no county record, image, or index page could be opened.
- The **certified source images and index pages are not present** in the cloud checkout; they reside on the operator's local drives.

Verification therefore operated on authorities (5)–(6) plus **independent internal controls** (below). Because the four highest authorities were unavailable, **no instrument was marked `VERIFIED`**, and every county-record fact is labeled **"Unable to verify from official county records."**

## 2. Status vocabulary and how it was applied

The mandate's status set was applied conservatively:

| Status | Applied when |
| --- | --- |
| `LIKELY MATCH` | Instrument is image-backed (pixel-verified by prior work against a local image, an image-backed confirmatory conveyance, or a countywide instrument). Strongest status attainable here. |
| `PARTIAL MATCH` | Supported only by county index metadata and/or local index reconciliation; no instrument image or schedule reviewed. |
| `VERIFIED` | **Not used** — requires authorities (1)–(4), which were unreachable. |
| `NOT FOUND` / `WRONG *` / `DUPLICATE` / `CORRECTED RECORDING` / `SUPERSEDED` | Reserved for county-record comparison; not assignable without the official record. Index-level duplicate/out-of-order conditions were tracked separately. |

## 3. Independent controls actually executed

1. **Cryptographic provenance** — recomputed SHA-256 of the primary workbook and compared to the hash recorded in the release documents. Result: **match**.
2. **Candidate selection audit** — compared the competing workbook candidates by live-formula count and sheet visibility to confirm the correct primary was chosen.
3. **Spreadsheet structural QA** (openpyxl) — for every workbook: formula census, formula-error scan (`#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, `#NAME?`), hidden sheets/rows/columns, merged-cell census, hyperlink audit, duplicate-row detection, and tract-acreage arithmetic.
4. **Cross-format integrity** — confirmed the project's xlsx ↔ csv ↔ json key sets, schemas, and primary-key uniqueness reconcile (validation status: PASS).
5. **Evidence-class audit** — classified every run-sheet instrument row by evidence strength and confirmed that no metadata-only row was used to assert title, ownership, WI, NRI, royalty, net acres, or HBP.
6. **Gap / missing-document review** — independently re-reviewed the open-items set for genuineness and severity ranking.

## 4. Anti-fabrication rules enforced

- No ownership, acreage, or decimal interest was invented, estimated, or balanced.
- Blank interest fields were preserved as **OPEN**, never coerced to zero.
- Surface owners were never presented as mineral owners; historical patentees/entrymen were never presented as present owners.
- A specific instrument (or an explicit "unable to verify") backs every statement in the Internal reports.

## 5. Reproducibility

The verification is reproducible from: the primary workbook, the index master, the reconciliation/claims artifacts, and this procedure. To complete authorities (1)–(4), re-run where **OKCountyRecords is reachable** or where the **certified `Images/` set and index pages are mounted**, then re-grade every register row and index entry.

## 6. Legal posture

This work organizes evidence and prepares draft work product. Under Oklahoma law, a marketability opinion on this section is legal work requiring a licensed attorney working from the certified county record. Nothing produced here is a title opinion or certified abstract.
