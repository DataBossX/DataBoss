# Test results (counts only; no client data)

Environment: Linux, Python 3.13, LibreOffice headless + Poppler, Carlito (Calibri-metric). **No Excel/Word/Acrobat.**

## Unit/integration tests
`python3 -m pytest -q tests` -> **8 passed** (synthetic donor; donor passes own profile; 9 planted defect classes caught with cell refs;
conform leaves inputs byte-identical and never invents values; XLSX->ODS parity 0; zip integrity/SHA/internal-leak; discover ranking; row-height estimator).

## Donor self-test (Section 11 index, 476 data rows, byte-exact copy verified by zip CRC)
format 0 errors, content 0 errors against its own profile. Row-height rule reproduces 453/476 donor heights exactly.

## Deliberately damaged copy of the donor (12 planted defect classes)
All 12 detected with exact cells. After `conform`: format 0 errors (XLSX and ODS), parity XLSX vs ODS 0 errors; the only residuals are the 4
non-inventable content items (placeholder, blank, impossible date, duplicate), listed in `needs_human`.

## Real sources vs Section 11 donor (before -> after conform, format errors)
| Section | Source | Before | After XLSX | After ODS | Parity | PDF |
|---|---|---|---|---|---|---|
| 13 | S13_County.ods (sheet `Index`, 80 rows) | 1294 | 1 | 1 | 0 | 3 flagged cells, 5 pages landscape Letter |
| 31 | S31_County.xlsx (sheet `Index`, 30 rows) | 386 | 1 | 1 | 0 | 0 errors, 2 pages landscape Letter |
The 1 remaining format error on each is the blank `Date Posted Thru` (real date required; not invented). Remaining content items are human decisions
(placeholder text, multi-date cells, ranged Book-Pages, over-long metadata, text left in Grantee/legal cells).

## Bugs the tests found in the toolkit itself (all fixed)
ODS reader: column-default styles, LibreOffice folded empty runs, master-page layout selection; XLSX border `None`; date vs datetime comparison;
`\b` section regex dropping `S13_...` names; role order (BLM before county); Excel width unit conversion; false-positive numfmt/row-height checks.
