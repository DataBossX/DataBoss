# DataBossX — Validation & Repair Agent

An agentic "perfection loop" for oil & gas mineral-title workbooks. It ingests an
`.xlsx`, validates every data gate, applies **only safe, source-derivable** repairs
via drawing-preserving XML surgery, recalculates with LibreOffice, and loops until
the report is client-ready **or halts and escalates to a human examiner** — it
never fabricates title facts.

Built and verified against Section **31-12N-24W, Roger Mills County, OK**
(Prospect 25-004, 637.42 gross acres, ten tracts, Alexander 1-31 well).

## Governing rules (Golden Law)
1. AI does the labor; the Examiner approves risk.
2. Every action leaves proof (append-only SQLite audit + evidence cache).
3. No fabricated legal facts — un-sourced needs escalate, never guess.
4. Immutability: no overwrites; every change emits `report_vN+1.xlsx`.
5. Production-grade, fully typed code.

## Layout
```
validation_agent/
  config.py            constants (637.42 ac, tract acreages, $100 cap, tolerances)
  models.py            typed vocabulary (enums + dataclasses)
  memory/              append-only SQLite: db, audit_log, spend_ledger
  ingestion/           workbook_map + typed sheet views
  validation/          5 gates: G1..G5 + suite/scorecard
  repair/              xml_surgery, recalc_engine, safe_fixes, taxonomy
  source_verification/ okcr_client (curl Basic Auth), evidence cache
  reporting/           audit_report, certification
  orchestrator.py      the Perfection Loop state machine
  app.py               Streamlit dashboard
  cli.py               `python -m validation_agent.cli run <wb.xlsx>`
  tests/               per-phase suites (30 tests, run on the real workbook)
```

## Quality gates
| Gate | Rule |
|------|------|
| G1 Interest Conservation | every instrument column conserves (sheet's own SUBTOTAL guards, no RECHECK) |
| G2 Pro-Rata Footing | each tract REPORT TOTAL == acreage (±0.01); Σ == 637.42 |
| G3 Chain Continuity | no orphan grantor (conveys out with no prior vesting) |
| G4 Instrument Audit | every line traces to a source; coverage == 1.0 |
| G5 OGL Register | unique numbers, bijective book/page, no phantom refs |

## Run
```bash
export DATABOSSX_ROOT=D:/Desktop/DataBossX          # optional; defaults to repo
export OKCR_API_KEY=…                                # for source verification
python -m validation_agent.cli run "report.xlsx" --max-iters 25
streamlit run validation_agent/app.py               # dashboard
pytest validation_agent/tests -q                    # 30 tests
```

## Proven implementation constraints (why the code is shaped this way)
- **Writes are XML surgery, never openpyxl** — openpyxl drops the embedded map,
  drawings, and threaded comments on save.
- **LibreOffice needs `OOXMLRecalcMode=0`** in a private profile or `--convert-to`
  keeps stale cached values (the recalc engine stamps this automatically).
- **Shared formulas are unshared** (relative refs translated) before editing a cell
  inside their range, or Excel renders `#REF!`.
- **`calcChain.xml` is dropped and `fullCalcOnLoad` set** on every emitted version.
- **OKCountyRecords uses curl Basic Auth** (key as username); it checks
  `free_to_view` and the spend ledger before any charge, and degrades to
  `SourceUnavailable` (→ escalation) when the host is unreachable.

## Two proven terminal behaviors
- **Repairs and certifies.** Seed a truncated footing SUMIF and the loop detects
  the G2 break, applies a SAFE `extend_footing_range` fix (derived from the grid's
  own dimensions), recalculates, re-validates to green, and emits a
  `*_CERTIFIED.xlsx` + final title picture — with the embedded map byte-identical.
  (`tests/test_p7_convergence.py`.)
- **Escalates instead of fabricating.** On the delivered workbook,
  `final state: ESCALATED` — G2/G4/G5 pass; G1 (7 ARTI columns) and G3 (orphan
  grantors) surface as WARN. Those gaps need recorded instrument images (OKCR/OCC),
  so the loop halts with a full proof trail rather than inventing interests — the
  intended, honest terminal state.

Analyzers (`repair/analyzers.py`) are what let a failure become auto-fixable: an
analyzer attaches a SAFE `FixPlan` only when the repair is derivable from workbook
structure. No analyzer, no auto-fix — the failure escalates.
```
