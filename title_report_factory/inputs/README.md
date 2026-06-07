# inputs/

Place source records for the run here, then run the pipeline. Supported:

- **PDF** — county-recorded instruments (text or scanned; scanned needs OCR)
- **Images** — `.png/.jpg/.tif` (needs OCR)
- **Excel** — prior workbooks, runsheets, indexes, "from kellpro" / source-data,
  Well Data sheets, and the **template workbook** named in the config
- **Text/CSV** — extracted text or tabular exports

Files are content-hashed for deduplication and logged in
`outputs/source_inventory.json`. Original files are never modified.

For the Section 27 Diversified run, add (names referenced by the config):

- `11N 25W 27 Diversified Cursory Report 6-6-2026.xlsx`
- `11N 23W 10 - Shanwee Cursory - 05-21-2026.xlsx` (style template)
- `11N_25W_27_Final_Cursory_Title_Report.xlsx` (authoritative source)
- any related recorded instruments / runsheet exports
