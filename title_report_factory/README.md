# title_report_factory

A reusable, config-driven pipeline that turns county records + a source
workbook into a finished **cursory title report** Excel workbook, plus
machine-readable index, confidence, and curative-issue artifacts.

It was built to run repeatedly for any section, and is first applied to
**Diversified's interest in Section 27-11N-25W, Beckham County, Oklahoma
(Cherokee formation)**.

## Truth rule (non-negotiable)

> Perfect is the target, but never fake perfection. Unknown is better than wrong.

Every record carries a **source**, a **confidence score (0-100)**, and an
**issue note** when uncertain. Capabilities that are not available in the
runtime are **detected and logged as limitations, never faked**:

- **OCR** of image-only PDFs runs only when `pytesseract`/`pymupdf` (+ system
  `tesseract`/`poppler`) are installed; otherwise the PDF is logged as a
  source-of-record and the structured index is used instead.
- **Live OKCountyRecords download** runs only when explicitly enabled in config
  *and* authorized credentials are in `.env`; otherwise it is skipped and noted.
- The **multi-pass tournament** uses deterministic heuristic review passes; a
  real multi-LLM backend is used only when API keys are present.

The overall confidence is **honestly capped (≤68)** because this is an
index/record-level cursory run: no recorded instrument images, lease schedules,
or OTC production were independently verified.

## Install & run

```bash
pip install -r requirements.txt
python -m title_report_factory run --config configs/section_27_diversified.json
```

The command prints the final JSON completion summary to stdout and writes all
artifacts to `outputs/`.

## Architecture

```
config_loader ─► file_inventory ─► okcounty_browser_downloader (optional)
        │
        ▼
   ocr_engine (capability-aware)
        │
        ▼  parallel extraction passes (ThreadPoolExecutor)
   ogl_analyzer · well_data_collector · chain_of_title_builder
        │
        ▼
   index_builder ─► multi_ai_tournament_reviewer (facts / effect / skeptic)
        │
        ▼
   quality_control ─► excel_template_writer ─► final_report_exporter
```

Supporting extractors: `legal_description_extractor`, `party_and_date_extractor`,
`interest_extractor`, `document_classifier`, `source_reader`.

## Inputs (kept local, not committed)

| Role | File |
|------|------|
| Source workbook (prior analysis) | `target_27_diversified.xlsx` |
| Style/structure template | `template_10_shanwee.xlsx` (Section 10) |
| Public-record context (OCC/BLM) | `context_public_records.xlsx` |
| Project notes | `project_notes.xlsx` |
| Scanned index (source-of-record) | `index_27.pdf` |

## Outputs

- **`Diversified_Section_27_11N_25W_Beckham_County_OK_Cursory_Title_Report.xlsx`**
  with sheets: Overview, Title, PLAT, Run Sheet, OGL, Well Data, Index Text,
  Source Notes, Confidence Summary, Curative Issues.
- `source_inventory.json` — every input file with SHA-256, size, page count.
- `index_text.json` / `index_text.txt` — the full consolidated instrument index.
- `confidence_summary.json` — overall, per-sheet, and per-document scores + QC.
- `curative_issues.json` — missing documents & curative items.
- `ocr_cache.json`, `sources_used.json`, `completion_summary.json`.

## Tests

```bash
python -m pytest tests/ -q
```

Covers date/party/royalty/legal parsing, the document classifier, the
section-wide vs. quarter-call regression, and an end-to-end check that the
workbook is produced with all required sheets and no blank key cells.

## Reuse for another section

Copy `configs/section_27_diversified.json`, change `subject_property`, point the
`inputs` at the new workbooks, and run. The sheet maps let you adapt to
differently-named source tabs without code changes.
