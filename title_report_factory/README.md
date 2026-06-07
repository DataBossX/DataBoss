# title_report_factory

A reusable, **honesty-first** workflow for building cursory (non-attorney)
title-report workbooks for a single PLSS tract (Section / Township / Range).

It only reports what it can tie to a source: a cell in a prior workbook, OCR
text from a scanned instrument, or a logged public record. Where it has no
support it writes `Unknown` / `Needs Review` and raises a Curative Issue — it
never fabricates instrument numbers, parties, dates, leases, wells, or
interests.

> ⚠️ Output is a **cursory** report from available records and OCR review, not a
> formal attorney title opinion. Every flagged issue requires attorney review
> and county-record confirmation.

## Usage

```bash
python -m title_report_factory run \
    --section 27 --township 11N --range 25W \
    --county Beckham --state OK --target-owner Diversified \
    --source-dir ./sources --out-dir ./output
```

Drop your inputs into `--source-dir` first:

* Prior workbooks — the Section 10 example, any existing Section 27 workbook, a
  KellPro export, an index/runsheet (`.xlsx` / `.xls`).
* Scanned instruments — deeds, leases, assignments, releases (`.pdf`, `.tif`,
  `.png`, `.jpg`).
* OCR sidecar / exported text (`.txt`, `.csv`, `.json`, `.md`).

Each run writes a timestamped folder under `--out-dir` containing the workbook
and a `run_summary.json`.

### Optional: authorized record collection

```bash
export OKCOUNTY_API_KEY=...        # your authorized key
python -m title_report_factory run ... --collect-records
```

This is **gated**: with no credentials it does nothing and says so. It never
bypasses paywalls, CAPTCHAs, logins, or rate limits, and logs every search.
Authenticated search/download is delegated to the existing
`doto_image_commander` OKCountyRecords client.

## Pipeline

1. `inventory.py` — scan `--source-dir`, classify each file.
2. `excel_reader.py` — map prior-workbook rows to instruments.
3. `ocr.py` — embedded-text first (pdfplumber/PyMuPDF), then Tesseract OCR with
   preprocessing; degrades honestly when no engine is installed.
4. `classify.py` — heuristic document-type + field extraction (instrument no.,
   book/page, dates, tract relevance).
5. `records.py` — optional, gated public-record collection.
6. `analysis.py` — assemble chain/interest view + confidence scoring.
7. `qc.py` — four QC passes (Source Completeness, OCR/Extraction, Title Logic,
   and the Excel Final Check in `workbook.py`).
8. `workbook.py` — render 10 styled sheets and export `.xlsx`.

## Output sheets

Overview · Title · PLAT · Run Sheet · OGL · Well Data · Index Text ·
Source Notes · Confidence Summary · Curative Issues.

## Optional dependencies

Core run needs only `openpyxl`. For OCR/scan support install any of:
`pdfplumber`, `PyMuPDF` (`fitz`), `pytesseract` + `Pillow` (and the `tesseract`
binary). Missing engines are reported, not silently ignored.

## Confidence scale (0–100)

| Range  | Meaning |
|--------|---------|
| 95–100 | Direct source, clear OCR, unambiguous effect |
| 85–94  | Strong support, minor uncertainty |
| 70–84  | Good support, one weak link |
| 50–69  | Useful, needs human verification |
| 25–49  | Weak / conflicting |
| 0–24   | Not reliable |
