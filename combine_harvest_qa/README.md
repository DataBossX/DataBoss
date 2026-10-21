# Combine-Harvest QA toolkit (CH185443)

Deterministic, local-only QA and format conforming for Combine-Harvest abstract packages, measured against a
finished Overtime donor (Section 11 by default). No network, no paid APIs, no credentials. Inputs are never modified.

## What it does
| Command | Purpose | Report |
|---|---|---|
| `profile` | Extract donor rules (fonts, borders, alignment/wrap, widths, row-height rule, date format, print setup, header block, Book-Page shapes, tolerated blanks) to JSON | `profile_*.json` |
| `check` | Cell-level **format** + **content** checks on an ODS/XLSX | `report_format.json`, `report_content.json` |
| `parity` | ODS vs XLSX value/type/style differences, cell by cell | `report_parity.json` |
| `pdf` | Real PDF geometry: page size/orientation, clipped text, margin/bottom overflow, repeated headings, workbook-text-in-PDF | `report_pdf.json` |
| `render` | Real pages: LibreOffice -> PDF -> PNG + pixel diff vs donor (uses COPIES) | `report_render.json`, PNGs |
| `letter` | Certification letter: geometry, fonts, wording vs donor template, preparation / posted-thru dates | `report_letter.json` |
| `package` | ZIP integrity (CRC), SHA-256, required client files, internal-QA leakage | `report_package.json`, `package_manifest.json` |
| `conform` | Build donor-matched **candidate** XLSX + ODS and a change log; never invents values | `*_changes.json` |
| `discover` | Rank newest/best files per section from a Drive metadata listing; flags foreign owners and header-only stubs | JSON |

Every finding has `section, check, severity, file, sheet, cell, expected, actual`.

## Quick start
```bash
pip install openpyxl lxml pdfplumber python-docx pillow   # + LibreOffice and poppler-utils for render/pdf
python3 chqa_run.py profile  DONOR.ods -o profile.json
python3 chqa_run.py check    CANDIDATE.xlsx --profile profile.json --out out/S13/after --posted-thru 2026-07-09
python3 chqa_run.py conform  SOURCE.ods --profile profile.json --out-xlsx out/S13/candidate/S13_Index.xlsx --sheet Index
python3 chqa_run.py parity   out/S13/candidate/S13_Index.xlsx out/S13/candidate/S13_Index.ods --out out/S13/parity
python3 chqa_run.py render   out/S13/candidate/S13_Index.ods --donor DONOR.ods --out out/S13/render
python3 chqa_run.py pdf      out/S13/render/pdf/candidate_S13_Index.pdf --workbook out/S13/candidate/S13_Index.ods --orientation landscape --margins 0.3 0.3 0.7 0.7 --out out/S13/pdf
python3 chqa_run.py letter   LETTER.docx --donor DONOR_LETTER.docx --prepared 2026-10-20 --posted-thru 2026-07-09 --out out/S13/letter
python3 chqa_run.py package  S13.zip --section 13 --blm WYW-153528 WYW-153681 --out out/S13/package
python3 chqa_run.py discover drive_listing.json --sections 13 31 --me you@example.com --since 2026-10-19T00:00:00Z -o ranked.json
python3 -m pytest -q tests
```
Any section: change the paths. BLM sheets: `profile --kind blm` on a donor BLM index, then `check --file-no WYWnnnnnn`.
Exit code is non-zero when errors are found, so it can gate a package.

## Checks implemented
Format: sheet name/count, metadata labels + styles, header text/order/style, **extra columns**, column widths, row-height
vs autofit (calibrated: 453/476 exact on the Section 11 donor), per-cell font/colour/fill/border/alignment/wrap/shrink/number format,
landscape/margins/fit-to-width, no freeze panes / repeated headings / merged cells.
Content: blank or Unknown/TBD/N-A substantive cells (blank tolerated only where the donor itself has blanks: Book-Page, Date of Doc),
metadata placeholders and over-long metadata, invalid/text/implausible dates, wrong date format, Rec Date before Doc date or after posted-thru,
Doc No stored as text, unexpected Comments or cell notes (only blank or exactly `missing image`), duplicate Doc No/Book-Page identities,
Book-Page shapes not seen in the donor, missing source links (`--links` CSV `row_key,source`), BLM Part/Page ordering and integer types,
federal File No (`WYW######`, or exact `--file-no`).

## Policy (what conform will and will not do)
Re-styles; converts date text to real dates and digit text to integers; trims whitespace; drops non-donor columns (logged);
removes non-`missing image` comments (logged). It **blanks** placeholders only where the donor allows blanks (logged, flagged "verify against the image").
It never fills, guesses or rewrites facts: everything else lands in `needs_human` in `*_changes.json`.

## Honest limits
- **Microsoft Excel, Word and Adobe Acrobat were not available** where this was built (headless Linux). All rendering is LibreOffice + Poppler and says so in
  `report_render.json` (`"renderer": "LibreOffice headless (NOT Microsoft Office)"`). No Office parity is claimed. On the Windows PC, re-open
  candidates in Excel/Word and export PDFs there; the same `pdf` / `letter` checks then run on the real Office output.
- The Section 11 donor ODS stores **no font size** (and no paper size). Conform defaults to Calibri 11 (`--font-size`) and the renderer adds Letter landscape to a *copy* of the donor.
- Visual diffs compare layout (header block, grid, borders); different row counts legitimately change page content.
- `cell_text_missing_in_pdf` tests first/last token per cell line; it is a smoke test for clipping, not OCR.
- Letter wording check masks dates, STR, serials, counts and county names, then requires paragraph-for-paragraph equality with the donor letter.
- `discover` ranks metadata only. Name-based "best" is weak: a 1 KB sheet named `..._100pct` is flagged `possible_stub`; open it.
- Keep `out/` (client data) out of git; it is git-ignored.

## Donor notes (verified against the finished Section 11 package)
- `Overtime_Examples_11_13_15.zip` SHA-256 `abcb8e81eac185c15669f82c1ec81c9aa0528a13a56428c61202b56d84dd1373` (929,863 bytes, CRC ok) matches the recorded value.
  Verify any donor with `python3 chqa_run.py package DONOR.zip --section 11 --sha256 <recorded>`.
- BLM style donors: use `S11_BLM_WYW051704.ods` or `S11_WYW-047318...ods` (10 columns A:J). `S11_WYW-005955...ods` is an older 7-column layout
  (no File No / Comments / Part) and fails the A:J profile; do not use it as the BLM reference.
- The toolkit can prove gates 1-3 and 5 on bytes it is given. It cannot prove gate 4 (native Excel/Word/Acrobat print) or custody/examiner release.
