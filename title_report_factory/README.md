# Title Report Factory

A reusable, automated **cursory title report** pipeline. Drop county records,
runsheets, and prior workbooks into an `inputs/` folder, point it at a config,
and it gathers records, OCRs documents, classifies instruments, builds a
verified full-text index, analyzes the chain of title, fills a styled Excel
workbook, and exports a finished report.

> **Guiding rule:** never fake perfection. Every conclusion carries a source and
> a confidence score. **"Unknown" is better than "wrong."** When passes
> disagree or data is missing, the workbook says so instead of guessing.

## Quick start

```bash
pip install -r requirements.txt          # core libs are required; OCR/LLM optional
# (optional) install the tesseract system binary for image-only PDFs
# (optional) cp .env.example .env  and fill in keys to enable LLM / downloader

python -m title_report_factory doctor    # report which optional backends are available
python -m title_report_factory run --config configs/section_27_diversified.json
```

Run from the project root (the folder that contains the `title_report_factory/`
package and `configs/`).

## CLI

| Command | Purpose |
|---|---|
| `run --config PATH` | Full pipeline; prints the JSON completion summary. |
| `inventory --config PATH` | List/hash input files only (audit). |
| `doctor` | Show OCR / LLM / downloader availability. |

## Outputs (written to `outputs/`, never overwriting inputs)

- **Finished Excel workbook** with 10 sheets: Overview, Title, PLAT, Run Sheet,
  OGL, Well Data, Index Text, Source Notes, Confidence Summary, Curative Issues.
- `index_text.json` — full-text index
- `ocr_cache/` — extracted text per document
- `source_inventory.json` — every input file + SHA-256 (dedup audit trail)
- `confidence_summary.json` — per-sheet, per-document, and QC scores
- `curative_issues.json` — missing documents + curative items
- `completion_summary.json` — the final JSON result
- `download_log.json` — every external source/search used

## Architecture

```
config_loader → file_inventory → okcounty_browser_downloader (optional)
   → ocr_engine → document_classifier
   → extractors (legal_description / party_and_date / interest)  [parallel]
   → index_builder
   → multi_ai_tournament_reviewer (facts / title-effect / red-team passes)
   → well_data_collector · chain_of_title_builder · ogl_analyzer
   → excel_template_writer → quality_control → final_report_exporter
```

- **Parallel processing:** documents are OCR'd / classified / extracted
  concurrently (`parallel_workers` in the config).
- **Multi-AI tournament:** for each document, independent passes extract facts,
  analyze title effect, and red-team for gaps/contradictions. Agreement raises
  confidence; disagreement is flagged, never forced. An LLM variant of each pass
  runs automatically *iff* a key is configured; otherwise deterministic
  heuristics are used.

## Security

- Credentials are read **only** from the environment (`.env`), never config or
  code. See `.env.example`.
- Source documents stay local; the original files are never modified.
- Every download and external source is logged.

## Configuration

See `configs/section_27_diversified.json`. Key fields: `subject_property`
(section/township/range, county, entity), `input_dirs`, `output_dir`,
`template_workbook` (optional style source), `output_file_name`, and the
`enable_ocr` / `enable_llm` / `enable_download` toggles.

## Tests

```bash
python -m pytest title_report_factory/tests -q
```

Covers classification, legal-description / party / date / interest extraction,
date formatting, Excel export (sheet presence, frozen panes, real date cells),
and a full end-to-end empty-inputs run.

## Note on the Section 27 run in this repository

The named source workbooks (`11N 25W 27 Diversified ...`, the Shanwee template,
the Final Cursory report) were **not present** in this execution environment, and
no authorized online source was reachable. Honoring the truth rule, the pipeline
produced a fully-structured **empty-state** workbook with every cell marked
`Unknown` / `Not Found` / `Needs Review` rather than fabricated title data. Place
the real documents in `inputs/` and re-run to generate the populated report.
