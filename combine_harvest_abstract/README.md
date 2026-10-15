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

## Still open

These packages are qualified working abstracts. They are not signed, not a title opinion, and not a client release. Judgment, lien, mortgage, and civil-suit searches were not performed. Assessor and treasurer reports are marked N/A. Sections 19, 30, and 31 do not have an official starting date or posted-through date. Section 30 instruments 142117, 174634, and 309041 stay unapplied, and 169051 stays on hold for missing folio 363, because those complete index fields were not in the selected parent.

Rebuild with:

```bash
python3 combine_harvest_abstract/scripts/finish_packages.py
```

The script reads the eight source packages from `/tmp/ch/in`.
