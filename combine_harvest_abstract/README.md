# Combine-Harvest abstract packages

Finished on October 15, 2026, in the layout of the completed Overtime abstracts (Campbell County Sections 11, 13, and 15).

Each section folder contains:

- the county index, with metadata in rows 1–7, a blank row 8, headings on row 9, and entries from row 10
- a federal index for every serial that was already in that section’s client package
- an 11-column abstract checklist in the Overtime three-block layout, Calibri 11, with every checklist cell filled
- an unsigned certification letter headed `Section N Abstract Certification Letter`

## What “filled” means

Columns A through H on every index entry now contain a value. Where the source package had a blank fact cell, the finish writes **Unknown**. Existing parties, dates, book and page, and legal descriptions were not changed, and no new instrument was added. The Comments column was left as it was. Unknown is not a zero and it is not a finding that nothing was recorded.

Sections 6, 7, 13, 18, and 24 use the October 15 client indexes. Sections 19, 30, and 31 use the partial unsigned packages. Those three stay limited to the rows that already had authenticated originals.

## Counts

| Section | Status | County entries | County Unknown cells | Federal indexes | Federal entries | Blank cells filled |
| --- | --- | --- | --- | --- | --- | --- |
| 6-47N-76W | Qualified unsigned | 124 | 12 | 0 | 0 | 12 |
| 7-47N-76W | Qualified unsigned | 192 | 8 | 1 | 143 | 285 |
| 13-47N-77W | Qualified unsigned | 238 | 56 | 5 | 281 | 447 |
| 18-47N-76W | Qualified unsigned | 136 | 6 | 1 | 168 | 342 |
| 19-47N-76W | Qualified partial | 2 | 0 | 0 | 0 | 0 |
| 24-47N-77W | Qualified unsigned | 346 | 57 | 4 | 112 | 223 |
| 30-47N-76W | Qualified partial | 1 | 0 | 0 | 0 | 0 |
| 31-47N-76W | Qualified partial | 4 | 1 | 0 | 0 | 0 |

`Combine_Harvest_Finish_Reconciliation.xlsx` lists every former blank cell, the format comparison, and the items that remain open. `SHA256_MANIFEST.txt` is the hash of each delivered file.

## Verified inventory, October 15, 2026

Every index in this folder was opened and counted. Columns A–H have no blank fact cells. A missing fact is the word Unknown.

| Section | County spreadsheet rows through the last entry | County data rows | County Unknown cells | BLM files | BLM documents | BLM parts |
| --- | --- | --- | --- | --- | --- | --- |
| 6 | 133 | 124 | 12 | 0 | 0 | 0 |
| 7 | 201 | 192 | 8 | 1 (WYW-131225) | 143 | 5 |
| 13 | 247 | 238 | 56 | 5 | 281 | 11 across the five files |
| 18 | 145 | 136 | 6 | 1 (WYW-133620) | 168 | 5 |
| 19 | 11 | 2 | 0 | 0 | 0 | 0 |
| 24 | 355 | 346 | 57 | 4 | 112 | 10 across the four files |
| 30 | 10 | 1 | 0 | 0 | 0 | 0 |
| 31 | 13 | 4 | 1 | 0 | 0 | 0 |

Each checklist is 9 spreadsheet rows (6 of them used) in Calibri 11. Each section has one unsigned letter. Sections 19, 30, and 31 now show index dates as M/D/YYYY.

Instrument image files from the October 13 census, counted as PDF files and the page images inside them:

| Section | Instrument PDFs | Pages | Tract-index pages | Standalone images in the later raster census |
| --- | --- | --- | --- | --- |
| 6 | 124 | 7,540 | 7 | 0 |
| 7 | 191 | 9,081 | 11 | 0 |
| 13 | 228 | 8,980 | 17 | 1 |
| 18 | 136 | 2,885 | 10 | not in that four-section raster table |
| 24 | 349 | 9,568 | 25 | 56 |

Do not add the raster-census page totals. Those files are shared across sections. The shared union is 917 source PDF paths, 663 distinct PDF bodies, 14,614 physical pages, and 57 standalone image paths. The part-by-part BLM split and the open list are on the `Verified inventory` sheet of `Combine_Harvest_Finish_Reconciliation.xlsx`.

## Still open

These packages are qualified working abstracts. They are not signed, not a title opinion, and not a client release. Judgment, lien, mortgage, and civil-suit searches were not performed. Assessor and treasurer reports are marked N/A. Sections 19, 30, and 31 do not have an official starting date or posted-through date. Section 30 instruments 142117, 174634, and 309041 stay unapplied, and 169051 stays on hold for missing folio 363, because those complete index fields were not in the selected parent.

Rebuild with:

```bash
python3 combine_harvest_abstract/scripts/finish_packages.py
```

The script reads the eight source packages from `/tmp/ch/in`.
