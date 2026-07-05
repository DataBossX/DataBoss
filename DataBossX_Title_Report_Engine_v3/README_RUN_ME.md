# DataBossX Title Report Engine v3 — RUN ME

Evidence-based cursory title report engine for
**Section 31, Township 12 North, Range 24 West, Roger Mills County, Oklahoma.**

> **Core rule: no evidence, no fabricated answer.** Where the runsheet / OGL
> schedule / template does not support a fact, the engine flags the row for
> examiner review and highlights the assumption **yellow** — it never invents an
> owner, an OGL number, a book/page, acreage, or a final ownership claim.

## Quick start (Windows)

1. Put this `DataBossX_Title_Report_Engine_v3` folder inside your **Horizon**
   folder (the one that holds your runsheet / template / OGL files).
2. Double-click **`run_engine.bat`**.
   It creates a venv, installs requirements, runs the engine against the Horizon
   folder (the parent of this engine), and prints where the report landed.

## Quick start (any OS)

```bash
cd DataBossX_Title_Report_Engine_v3
python -m pip install -r requirements.txt
python app.py --root "/path/to/Horizon"      # defaults to this engine's parent folder
```

Prove the chain math against a clearly-labeled **synthetic** fixture:

```bash
python app.py --root . --demo
python -m pytest tests/test_engine.py -v
```

## What it does (maps to the mission tasks)

| Stage | Module | Output |
| --- | --- | --- |
| 1 Discover & rank files | `engine/discover.py` | `logs/FILE_INVENTORY.xlsx`, `logs/SOURCE_FILE_RANKING.xlsx` |
| 6–7 Template + Tract 1 profile | `engine/tract1_profile.py` | `logs/TEMPLATE_PROFILE.xlsx`, `logs/TRACT1_PROFILE.xlsx` |
| 8 Runsheet parse | `engine/parser.py` | `logs/PARSED_RUNSHEET_EVIDENCE.xlsx` |
| 9 OGL match | `engine/ogl_matcher.py` | `logs/OGL_MATCH_REPORT.xlsx` |
| 10 Chain engine (Decimal/Fraction) | `engine/chain.py` | `logs/CHAIN_CALCULATION_LEDGER.xlsx` |
| 11–12 Assumptions / notes | `engine/assumptions.py`, `notes.py` | `logs/ASSUMPTIONS_AND_REVIEW_FLAGS.xlsx` |
| 13 Final owners | `engine/verifier.py` | Title Sheet in the workbook |
| 14 Writer | `engine/writer.py` | the final workbook |
| 15 Audit log | `engine/audit.py` | `logs/SECTION31_AUDIT_LOG.xlsx` + Audit Log sheet |
| 16 Evidence score | `engine/chain.py` | `logs/EVIDENCE_SCORE_BY_TRACT.xlsx` |
| 17 QA | `engine/qa.py` | `logs/QA_VALIDATION_REPORT.xlsx` |
| 18 Final output | `app.py` | `../SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx` + timestamped backup |

## Reading the output

- **Final report** is written to the Horizon root:
  `SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx`.
- **Overview** tab is always first; then **Title Sheet**, one sheet per **Tract**
  (Tract 1 master style, OGL carried beside leased owners), then **Audit Log**,
  **Review Flags**, **Assumptions**, **Source Ranking**, **Evidence Score**,
  **QA Summary**.
- **Yellow** = a true unresolved assumption / review item. Nothing else is yellow.
- `logs/RUN_SUMMARY.md` is the human-readable run report.

## If your files aren't found

The engine ranks candidates by name + content. If it picks the wrong file (or
reports `NONE FOUND`), open `logs/SOURCE_FILE_RANKING.xlsx` to see why, then
either rename your file to include `runsheet` / `template` / `ogl`, or drop the
correct file into `data/input` (runsheet/OGL) or `data/template/template.xlsx`.

## PDF note

PDF text extraction needs a working `pdfplumber`/`pypdf` install. If the backend
can't load in your environment the engine records that OCR / manual extraction is
required for that file — it does not invent extracted data.
