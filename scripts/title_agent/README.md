# DataBossX — Title Validation & Repair Agent

Autonomous validation and safe auto-repair of the cursory title report for
**Section 31-12N-24W, Roger Mills County, Oklahoma** (Prospect 25-004 · 637.42
gross acres · 10 tracts · Alexander 1-31 well).

## The Golden Law

> AI handles the labor, the human Examiner approves the risk.

No quality gate is ever cleared by fabricating a legal fact. Concretely:

- **Append-only audit** — `audit_log` and `budget_ledger` are guarded by SQLite
  triggers that reject every `UPDATE`/`DELETE`. History cannot be edited, even
  by code that bypasses the Python layer.
- **No overwrites** — every automated fix mints a new `_vNNN` file; the
  `VersionController` refuses any path that already exists on disk.
- **Escalate, don't invent** — failures that would require an assumed heir,
  deed, Book/Page, or royalty halt the loop for the Examiner (Category B).
  Ambiguous failures escalate by default.

## Layout

| Module | Responsibility |
| --- | --- |
| `core/config.py` | Env-overridable paths and prospect constants |
| `core/memory.py` | `SQLiteManager`, `AuditLogger`, `VersionController`, `EscalationStore` |
| `core/taxonomy.py` | `Gate` and `FailureCategory` (the A/B split) |
| `core/loop.py` | `PerfectionLoop` state machine + `TaxonomyRouter` |
| `core/wiring.py` | Concrete adapters: `WorkbookGateSuite`, `SurgeonRepairer`, `OKCountySourceProbe`, `ColumnMap` |
| `__main__.py` | `register` / `run` / `status` CLI |
| `api/okcounty.py` | `CurlClient` (subprocess curl, Basic Auth), `DocumentVerifier`, `BudgetManager` ($100 cap) |
| `excel/xml_surgeon.py` | `ArchiveManager`, `CalcChainDestroyer`, `XMLPatcher` |
| `excel/recalc.py` | `LibreOfficeEngine` headless recalc + error scan |
| `data/ingestion.py` | `WorkbookMapper` — non-destructive topology of the 10 tracts, OGL, WI, runsheets, well tab |
| `validators/rules.py` | The six quality gates |
| `frontend/dashboard_data.py` | Tested read/resolve model for the UI |
| `frontend/app.py` | Streamlit dashboard (Scorecard, Audit Trail, HITL forms) |

## The six gates

1. **Interest Conservation** — every instrument column nets to `0.00000000`.
2. **Acreage Footing** — pro-rata net acres tie to each tract; gross sums to `637.42`.
3. **Chain Continuity** — grantor N == grantee N-1, no chronological gap.
4. **Source Verification** — every runsheet line traces to a verified OKCounty document.
5. **OGL Parity** — the OGL register reconciles with the WI sheets and runsheets.
6. **Execution** — LibreOffice recalc yields zero `#REF!`/`#N/A`/OOM.

## Configuration (environment)

| Variable | Purpose |
| --- | --- |
| `TITLE_AGENT_BASE_DIR` | Root for state (default: this package). Set to `D:/Desktop/DataBossX/scripts/title_agent` on the Examiner's workstation. |
| `TITLE_AGENT_DB_PATH` / `TITLE_AGENT_WORKBOOK_DIR` / `TITLE_AGENT_AUDIT_LOG` | Override individual state locations |
| `TITLE_AGENT_BUDGET_CAP` | Hard spend ceiling (default `100.00`) |
| `OKCOUNTY_API_KEY` | OKCountyRecords key (Basic Auth username, empty password) |

## Running

```bash
# Tests (also runnable per-module: python -m scripts.title_agent.tests.test_loop)
pytest scripts/title_agent/tests

# Run the agent against a workbook
python -m scripts.title_agent register "D:/Desktop/DataBossX/31-12N-24W.xlsx"
python -m scripts.title_agent map       # preflight: how columns map to the gates
python -m scripts.title_agent run       # certifies or halts for the Examiner
python -m scripts.title_agent status    # scorecard

# Dashboard
streamlit run scripts/title_agent/frontend/app.py
```

The `run` command attaches a live OKCounty source probe only when
`OKCOUNTY_API_KEY` is set, and enables Gate 6 only when LibreOffice is
functional. Retarget the workbook layout by adjusting `ColumnMap` in
`core/wiring.py` — the header-label aliases, not the validators.

**Mapping preflight.** Because `ColumnMap` matches columns by header label,
`run` first calls `WorkbookGateSuite.coverage()` and **refuses to proceed** if a
core gate (2 Acreage or 3 Chain) cannot read its inputs from a sheet that
exists — otherwise those gates would pass on no data and produce a false
`CERTIFIED`. Use `map` to see the per-gate mapping first and fix the aliases
against the real headers before running. `run --force` overrides the guard
(gates with unread inputs simply don't run).

**Retarget without editing code.** When `map` shows unresolved columns, supply a
JSON override instead of editing Python — pass `--column-map cm.json`, or drop a
`columnmap.json` in the base dir (auto-loaded). Only the fields you name are
overridden; unknown field names are rejected. Example:

```json
{ "grantor": ["from", "grantor"], "grantee": ["to", "grantee"],
  "net_acres": ["net mineral acres"] }
```

Valid fields: `grantor, grantee, date, interest_change, book, page, instrument,
tract, gross_acres, net_acres, interest_fraction, lessor, royalty, owner,
working_interest, nri`.

## Note on Gate 6 in CI

`LibreOfficeEngine.conversion_works()` is a functional probe. Some sandboxed
containers ship a `soffice` that runs but cannot load documents; there the live
recalc round-trip test skips honestly rather than fake a pass. On a workstation
with a working LibreOffice the full round-trip runs.
