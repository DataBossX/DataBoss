# Cursory Title Report Generator

A self-contained engine that turns a structured title-examination data model
into the full deliverable set described in the DataBoss report workflow — an
Excel workbook with every required tab plus the accompanying CSV/Markdown
artifacts. It runs end to end with **no live source access** using a clearly
flagged placeholder dataset for Section **31-11N-24W, Roger Mills County, OK**.

## Quick start

```bash
pip install -r title_report/requirements.txt

# Generate all deliverables from the bundled placeholder dataset
python -m title_report.generate --out title_report_output

# Override the report/run date
python -m title_report.generate --out title_report_output --date 2026-06-23
```

## Deliverables produced

| File | Contents |
| --- | --- |
| `<TRACT>_Cursory_Title_Report_<date>.xlsx` | Cover, Source Log, Runsheet, Abstractions, two Chain tabs (mineral/surface and leasehold/WI/burdens), Wells & HBP, Curative, **NRI-WI Matrix (live formulas)**, QA Dashboard, Missing-Unverified |
| `SOURCE_LOG.csv` | Every source consulted, with credential-required flag and page refs |
| `CURATIVE_LIST.csv` | Encumbrances/curative items by materiality, priority, status, action |
| `MISSING_OR_UNVERIFIED_INSTRUMENTS.csv` | Derived gaps: uncited rows, referenced-but-absent instruments, review flags |
| `QA_RESULTS.md` | Results of every QA gate and the finalization decision |
| `CHANGE_SUMMARY.md` | Change log; required for every revision after the first run |

## Design rules (enforced by `qa.py`)

- **No hallucinations.** Unknown fields stay `UNKNOWN`; they are never inferred,
  zeroed, or guessed.
- **Auditable fraction math.** NRI / WI / NMA use exact rational arithmetic
  (`fractions.Fraction`) and are mirrored as live Excel formulas, so every
  derived cell traces to its components. Blank inputs render `UNKNOWN`, not `0`.
- **No computed interest without basis language.** An ownership entry must carry
  exact governing text before any NRI/NMA is computed; QA fails otherwise.
- **Citation coverage.** Every material schedule row references a source.
- **Row reconciliation.** Workbook row counts must match the model.
- **Secrets scan.** Deliverables are scanned for keys / passwords / private keys.
- **Finalization gate.** A report is never marked FINAL while placeholder data is
  in use or any QA check fails.

## Module layout

```
title_report/
  models.py        dataclasses for the data model (UNKNOWN sentinel)
  fractions.py     exact rational math + Excel-formula builders
  sample_data.py   illustrative placeholder dataset (31-11N-24W)
  workbook.py      Excel workbook with all tabs, styling, filters, formulas
  deliverables.py  SOURCE_LOG / CURATIVE_LIST / MISSING / CHANGE_SUMMARY
  qa.py            QA gates -> QA_RESULTS.md
  generate.py      orchestrator + CLI (python -m title_report.generate)
  tests/           pytest suite (run: python -m pytest title_report/tests)
```

## Using real data

Replace `build_sample_report()` with a `TitleReport` populated from examined
records (set `ProjectConfig.is_placeholder=False`), then call
`title_report.generate.generate(rpt, out_dir=...)`. The same QA gates apply and
the report becomes FINAL-eligible once all checks pass.

> **Credentials.** Subscription portals (e.g. OKCountyRecords) are accessed via
> an approved credential manager — never pasted into prompts, code, or
> deliverables. The secrets scan guards against accidental leakage.
