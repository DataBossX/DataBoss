# `databossx` — the Command Center package

A thin, unit-tested **orchestration + economics + reporting** layer that unifies
the existing DataBossX engines into one project-based application. It does not
replace those engines; it wires them into a single end-to-end run.

```
resolve project ─▶ ingest & inventory (sha256 evidence) ─▶ extract text / OCR
   ─▶ chain OGL↔runsheet (horizon)  ─▶ mineral / WI / NRI (databossx.ownership)
   ─▶ defects & missing evidence    ─▶ Excel + PDF + dashboard
   ─▶ examiner worklist + run manifest + audit log
```

## Modules

| Module | Responsibility |
| --- | --- |
| `ownership.py` | **Exact-fraction** mineral / leasehold / working-interest / NRI calculator built on `horizon.interest`. The two governing identities (Σ mineral = 8/8, Σ WI = Σ NRI = leased fraction) are *checked and reported*, never forced. |
| `projects.py` | Registry of named projects (Horizon, Penterra, Roger Mills, Beckham, Ryder, + future) with layered root resolution (`--root` › `DATABOSSX_<KEY>_ROOT` › `DATABOSSX_ROOT` › default). |
| `command_center.py` | The end-to-end `run_project()` orchestrator + the ownership-sheet reader. Never raises for expected operational problems — they become a plain-language message on the result. |
| `excel_report.py` | Client-ready multi-sheet workbook (Summary, Runsheet, Mineral Ownership, Division of Interest, Defects, Evidence). |
| `pdf_report.py` | Client-ready paginated PDF (reportlab) with cover, tables, page numbers, draft/synthetic footer. |
| `dashboard.py` | Self-contained HTML dashboard (no external assets, theme-aware). |
| `backup.py` | Timestamped, non-destructive backup of prior deliverables. |
| `selfcheck.py` | `doctor` — plain-language PASS/WARN/FAIL health check + in-memory exact-math smoke test. |
| `demo.py` | Generator for the bundled **synthetic** golden project (100% invented; deliberately flawed so the defect machinery has something to catch). |
| `cli.py` / `__main__.py` | `databossx doctor | list | demo | run | calc`. |

## Run

```bash
python dbx.py doctor                        # health check
python dbx.py demo                           # build + run synthetic project
python dbx.py run --project horizon --root /path/to/files
python dbx.py calc --wi 1/2 --royalty 3/16 --orri 1/32
```

Or use the launchers: `DataBossX.bat` (Windows, menu-driven) / `run_databossx.sh`.

## The economics model (exact)

For each leased mineral owner the division of interest expands to:

| Party | Working interest | NRI |
| --- | --- | --- |
| Lessee (WI owner) | = leased mineral fraction | `mineral × (1 − royalty − ORRI)` |
| Lessor (royalty) | — | `mineral × royalty` |
| ORRI holder | — | `mineral × ORRI` |

Unleased owners are carried as open **mineral** rows. Every quantity is an exact
`fractions.Fraction`; a value the inputs don't support is left blank and the row
is flagged `review` — the calculator never fabricates to make 8/8 close.

## Design guarantees

- **No fabrication.** Undetermined ⇒ blank + review flag, never a guess.
- **Zero destruction.** Sources are read-only; output goes to a managed folder;
  prior deliverables are backed up before a rerun.
- **Human release gate.** Technical verification is not client release; every
  deliverable says so.
- **Graceful degradation.** A missing optional dependency (e.g. `reportlab`) or
  an absent input downgrades a feature with a plain-language note — it does not
  crash the run.

## Tests

```bash
python -m pytest tests/test_databossx_*.py -q
```

Covers: exact ownership math (mineral/WI/NRI, 8/8 checks, over-conveyance,
no-fabrication), report generation (Excel/PDF/dashboard, blanks not zero-filled),
project resolution, the doctor, and the full end-to-end run on the golden
project (all deliverables produced; every planted defect caught → RED).
