# Tract-ledger re-extraction gate

Use this when a unique-key or R6 comparison is blocked because document numbers
are the only identity on most rows. That ledger cannot correct itself. Return
to the page renders, capture book/page, recorded date, and parties, then rerun.

The gate does not open Drive, guess a neighbouring document number, or mutate a
canonical workbook.

## Checkable row

A row is checkable when it has either:

- a book/page locator, or
- a face-captured recorded date plus grantor or grantee

Modern Campbell filings may leave book/page blank. Those rows still pass when
the face supplied a recorded date and a party. Bare document-number rows fail.

## Commands

```bash
python3 -m horizon.reextraction_gate \
  --packet /path/to/tract-ledger-export.json \
  --output /path/to/reextraction-receipt.json
```

After every row is checkable, an isolated oracle (for example a source-bound
Section 13 workbook export) may be supplied. Cross-key proposals require
independent corroboration. The gate refuses the oracle while bare rows remain.

```bash
python3 -m horizon.reextraction_gate \
  --packet /path/to/reextracted-export.json \
  --oracle /path/to/oracle.json \
  --output /path/to/reextraction-receipt.json
```

House stable keys are `<docno>|<book>-<page>`. Feed those keys into
`horizon.occurrence_ledger` after this gate passes.

Compile crops from page renders without guessing a document number:

```bash
python3 -m horizon.page_render_export \
  --packet /path/to/page-render-crop-packet.json \
  --export /path/to/tract-ledger-export.json \
  --output /path/to/page-render-export-receipt.json \
  --bind-dir /path/to/page-renders
```

`expected_page_count` is writer-held (Section 11 historically used 14 page
renders; this module does not hard-code that). Each crop must hash-bind to
its page. Bare document-number crops are preserved so the re-extraction
gate can still fail them.

Hash-bound federal PDF page census (Part 4 empty-text hold):

```bash
python3 -m horizon.pdf_census \
  --packet /path/to/pdf-page-census-packet.json \
  --bind-dir /path/to/federal-pdfs \
  --output /path/to/pdf-census-receipt.json
```

Image-only PDFs can pass the hash/count bind while `empty_text_files` stays
visible. Do not invent legal text from a page count.

Exit codes:

- `0`: every row is checkable
- `2`: a receipt was written, but bare or unparseable rows remain
- `1`: the export is malformed; no receipt is promised

`technical_pass` is not package release.
