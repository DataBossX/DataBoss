# Drop title source files here

Place inputs for a run in this folder (or any folder you pass to --source-dir):

- Prior workbooks: Section 10 example, existing Section 27 workbook, KellPro
  export, county index/runsheet (.xlsx/.xls)
- Scanned instruments: deeds, leases, assignments, releases (.pdf/.tif/.png/.jpg)
- OCR/exported text (.txt/.csv/.json/.md)

Then run, e.g.:

    python -m title_report_factory run \
        --section 27 --township 11N --range 25W \
        --county Beckham --state OK --target-owner Diversified \
        --source-dir ./sources --out-dir ./output
