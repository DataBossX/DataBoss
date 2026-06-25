# Title Report Builder

Turn a folder of source documents + a format-only template into a finished
**cursory oil & gas title report** (Excel). Production pipeline extracted from the
Roger Mills 31‑12N‑24W job and made reusable for any PLSS section.

> **Golden Law:** the AI does the labor, the human approves risk, every action
> leaves proof. The pipeline **never fabricates** owners, fractional interests,
> acreage, royalties, or legal descriptions. Unsupported cells are *flagged*, not
> invented. Secrets are loaded from `.env` and never logged or written into output.

---

## What it does

1. **Discover** — recursive source manifest (path, type, size, mtime, sha256).
2. **Extract** — Excel (openpyxl), PDF (PyMuPDF render + Tesseract OCR; auto-detects
   typed vs scanned), images (preprocess + OCR), text/markdown/docx.
3. **Foot & repair** — standardizes every tract's net-acre column to the canonical
   pro-rata formula so it **foots exactly to the tract acreage (D5)**, excluding
   "The Public"; replaces rounded conversion-decimals with **exact fractions**.
4. **Title logic** — normalizes aliquots, maps each instrument to its tract via the
   quarter-quarter geometry, builds chronological **grantor → grantee chains**.
5. **Assemble** — adds an **Index Evidence** sheet and **Chain of Title** sheet with
   working OKCountyRecords + internal navigation hyperlinks.
6. **QA** — scans for formula errors (`#REF!`…), broken link targets, and confirms
   every defined tract foots to D5.

Footing is an **allocation**, not a deed-by-deed derivation — and the report says so.

---

## Quick start (non-coder)

**Windows:** double-click **`RUN_APP.bat`**. On first run it finds Python, creates a
local `.venv`, installs dependencies, and opens the app in your browser. If Python
isn't installed it tells you exactly where to get it.

**macOS/Linux:** `./run.sh` (UI) or `./run.sh cli ...` (command line).

### Command line

```bash
python -m title_report_builder discover --project "/path/to/Roger Mills" --manifest manifest.csv
python -m title_report_builder ocr      --pdf index.pdf --out ./_work --dpi 300 --render
python -m title_report_builder foot     --workbook in.xlsx --out fixed.xlsx \
        --tracts "Tract 1,Tract 2,Tract 3,Tract 4,Tract 5,Tract 6,Tract 7,Tract 8"
python -m title_report_builder qa       --workbook fixed.xlsx
# end-to-end Roger Mills build (footing + index evidence + QA):
python -m title_report_builder.report.build_roger_mills in.xlsx out.xlsx evidence.json
```

---

## Configuration

- Section/tract geometry lives in `config.example.yml` (copy to `config.yml`). Each
  tract is defined by its 40-acre aliquots — change these to retarget another section.
- **Secrets** (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `LMSTUDIO_BASE_URL`, …) go in a
  `.env` file (e.g. the shared `DataBossX/.env`). Model routing prefers configured
  providers and **always falls back to an offline, deterministic mode** that never
  hallucinates — it returns "needs review" rather than inventing facts.

## Project layout

```
apps/TitleReportBuilder/
  RUN_APP.bat / INSTALL_OR_REPAIR.bat / BUILD_ROGER_MILLS_REPORT.bat / run.sh
  requirements.txt  config.example.yml  README.md  .gitignore
  title_report_builder/
    config.py  discovery.py  cli.py  app.py  __main__.py
    extractors/  excel_extractor  pdf_extractor  image_ocr  text_extractor
    report/      footing  title_logic  qa  formatting  workbook_builder  build_roger_mills
    models/      provider  offline  openai_provider  anthropic_provider
    utils/       logging · paths · security (secret redaction) · hashing
  tests/         test_footing.py
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| *Python not found* | Install Python 3.11+ from python.org and check "Add to PATH". |
| *Tesseract not found* | OCR needs Tesseract — UB-Mannheim build (Windows) or `apt install tesseract-ocr`. |
| *LibreOffice/recalc warning* | Optional; install LibreOffice to enable headless recalc verification. |
| *No model API key* | Fine — the app runs offline; model-assisted extraction is simply skipped. |
| *Permission denied on .xlsx* | Close the workbook in Excel before building. |
| *Corrupt source PDF* | Re-export/re-scan; the OCR step logs and skips unreadable pages. |

## Tests

```bash
pip install pytest && pytest -q
```
