# TitleFinisher architecture

```
titlefinisher/
  config.py              Config + Golden-Rule constants (19-sheet lock, exclusion regex, YELLOW)
  pipeline.py            Orchestration: run_offline() and run_online(); writes audit log + punch list
  __main__.py            CLI: offline | online | worklist | audit

  workbook/
    reader.py            build_worklist() — auto-discovers every open item from the sheet
    surgical_editor.py   SurgicalEditor — format-preserving XML cell writer / (un)highlighter
    auditor.py           audit() — full lock-set QC, returns (ok, issues, notes)

  ocr/
    ocr.py               ocr_pdf/ocr_image — PyMuPDF render + Tesseract, embedded-text fallback
    instrument_parser.py parse_index_page() (county index) + parse_instrument() (single doc)

  fetch/
    okcountyrecords.py   OkCountyRecords — instrument images by number/book-page + section sweep
    occ.py               OCC — RBDMS well row + Form 1002A hook + spacing
    otc.py               OTC — gross production + is_hbp() decision

  resolve/
    gap_resolver.py      find_source_in() — grantee-side source-in cross-reference
    index_db.py          build_index_db() — OCR the index PDF into an instrument database
```

## Data flow

**offline**  workbook → build_worklist → (index_db + runsheet rows) → find_source_in →
SurgicalEditor.unhighlight resolved gaps → audit → audit log + punch list.

**online**  workbook → build_worklist → for each open item: fetch (okcountyrecords / OCC /
OTC) → OCR → parse_instrument → SurgicalEditor fill/unhighlight → audit loop → outputs.
Every fill is backed by a saved file in `data/proof/`; unresolved items stay flagged.

## Why XML surgery instead of openpyxl save

openpyxl rewrites the whole package on save and drops the SVG map layer and threaded
comments this report relies on. SurgicalEditor rewrites only the touched worksheet XML
parts inside the zip, so media / drawings / comments / styles / merges / print settings /
tab order are byte-identical to the examiner's original.

## Extending to another section / county

Nothing is hard-coded to Roger Mills except defaults in `.env`. Point `--workbook`,
`--index`, `--county`, `--twprge`, `--section` at the new job. The 19-sheet NHE layout is
the assumed template; adjust `REQUIRED_SHEETS` in `config.py` if a different template is used.
