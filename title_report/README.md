# Cursory Title Report Generator

A self-contained engine that turns a structured title-examination data model
into the full deliverable set described in the DataBoss report workflow — a
polished, fully hyperlinked Excel workbook with every required tab plus the
accompanying CSV/Markdown artifacts. It runs end to end with **no live source
access** using clearly flagged illustrative datasets.

Two bundled tracts:

| Tract | `data_status` | Notes |
| --- | --- | --- |
| **31-12N-24W** (default) | `SPECIMEN` | Fully populated — every cell filled, gap-free chain root-patent→present, ownership reconciles to 8/8, all links live. |
| 31-11N-24W | `PLACEHOLDER` | Skeletal; demonstrates UNKNOWN handling. |

> Both are **illustrative models, not examinations of record title.** No live
> county/OCC/BLM/court records were pulled, so the chains and parties are
> internally-consistent fictions used to exercise the report end to end. The
> cover, Summary, and QA banners say so, and the report is never marked FINAL
> as a record-title opinion while `data_status != EXAMINED`.

## Quick start

```bash
pip install -r title_report/requirements.txt

# Default: the fully-populated 31-12N-24W specimen, dated 2026-06-25
python -m title_report.generate --out title_report_output --date 2026-06-25

# Choose a tract
python -m title_report.generate --tract 31-11N-24W --out title_report_output
```

## What "10,000× better" means here

- **Every cell filled** in the specimen — no UNKNOWN in the runsheet, a complete
  clause-level abstraction for each material instrument.
- **Working links throughout** (~120 in the specimen): a Contents tab linking to
  every sheet, citations linking to their Source Log row, instrument references
  linking to their Runsheet row, and out-links to the live public portals
  (OKCountyRecords, OCC, BLM GLO, OSCN, OTC, OK SOS, FracFocus).
- **Fully chained title**: mineral/surface and leasehold/WI chains are
  chronological and gap-free, with a continuity flag on every link.
- **Reconciling ownership**: the NRI-WI matrix uses live, fraction-formatted
  Excel formulas (royalty, working-interest, and ORRI roles) and a TOTALS row
  that proves minerals and NRI each equal 8/8.
- **Summary dashboard** with schedule counts, live reconciliation, HBP status,
  and curative counts by materiality.

## Deliverables produced

| File | Contents |
| --- | --- |
| `<TRACT>_Cursory_Title_Report_<date>.xlsx` | Cover, **Contents (linked)**, **Summary dashboard**, Source Log, Runsheet, Abstractions, two Chain tabs (mineral/surface and leasehold/WI/burdens), Wells & HBP, Curative, **NRI-WI Matrix (live formulas + reconciliation)**, QA Dashboard, Missing-Unverified |
| `SOURCE_LOG.csv` | Every source consulted, with credential-required flag and page refs |
| `CURATIVE_LIST.csv` | Encumbrances/curative items by materiality, priority, status, action |
| `MISSING_OR_UNVERIFIED_INSTRUMENTS.csv` | Derived gaps: uncited rows, referenced-but-absent instruments, review flags |
| `<TRACT>_Dashboard_<date>.html` | Self-contained interactive dashboard (nav, summary cards, computed-NRI ownership table with reconciliation, full schedules, QA badges) — no external assets |
| `QA_RESULTS.md` | Results of every QA gate and the finalization decision |
| `CHANGE_SUMMARY.md` | Change log; required for every revision after the first run |

## Real data: the DOTO feed

`title_report/adapters/doto.py` reads the **DOTO Image Commander** SQLite
database (`analyses` joined to `image_queue` / `downloads`) and assembles an
`EXAMINED` report for a Section-Township-Range from the actual analyzed
instruments — runsheet, abstractions, and a chronological chain.

```python
from title_report.adapters.doto import available_tracts, build_report_from_db
from title_report.generate import generate

tracts = available_tracts("doto_commander.db")          # discover STR tracts in the DB
rpt = build_report_from_db("doto_commander.db", "31", "12N", "24W",
                           report_date="2026-06-25", source_cutoff_date="2026-06-24")
generate(rpt, out_dir="title_report_output")            # workbook + HTML + CSVs + QA
```

The adapter uses only stdlib `sqlite3` (no dependency on the DOTO package) and
**invents nothing**: ownership interests are left empty rather than synthesized
without exact governing fractions, and that gap is flagged on the
Missing/Unverified schedule.

## In the app

`doto_image_commander/pages/7_Title_Report.py` adds a **Cursory Title Report**
page to the Streamlit app: pick a tract from the examined instruments in the DB
(or a bundled illustrative dataset), generate the workbook + HTML dashboard +
CSVs with QA in one click, preview the QA results and dashboard inline, and
download every deliverable.

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
  models.py                 dataclasses for the data model (UNKNOWN sentinel)
  fractions.py              exact rational math + Excel-formula builders
  sample_data.py            skeletal placeholder dataset (31-11N-24W)
  specimen_31_12N_24W.py    fully-populated specimen dataset (31-12N-24W)
  workbook.py               Excel workbook: tabs, links, dashboard, formulas
  deliverables.py           SOURCE_LOG / CURATIVE_LIST / MISSING / CHANGE_SUMMARY
  qa.py                     QA gates -> QA_RESULTS.md
  generate.py               orchestrator + CLI; TRACTS registry
  tests/                    pytest suite (run: python -m pytest title_report/tests)
```

## Using real data

Replace `build_sample_report()` with a `TitleReport` populated from examined
records (set `ProjectConfig.is_placeholder=False`), then call
`title_report.generate.generate(rpt, out_dir=...)`. The same QA gates apply and
the report becomes FINAL-eligible once all checks pass.

> **Credentials.** Subscription portals (e.g. OKCountyRecords) are accessed via
> an approved credential manager — never pasted into prompts, code, or
> deliverables. The secrets scan guards against accidental leakage.
