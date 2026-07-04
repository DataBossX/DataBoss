# DataBossX Automated Validation, Repair, Source Retrieval, Report & Export Agent

The human owns legal judgment. This software performs the labor: nondestructive
ingestion, math/formula validation with exact arithmetic, evidence collection,
**safe** workbook repair, report improvement, and examiner-ready escalation
packaging — all under an **append-only audit trail** and a **hard $100 spend cap**.

> **It never fabricates legal, title, probate, lease, ownership, instrument, or
> HBP facts.** Anything it cannot verify halts the automated path and escalates.

## What it will never do
- Overwrite a source workbook, PDF, image, prior report, DB, or version.
- Mutate audit history (UPDATE/DELETE are blocked in the DB engine itself).
- Spend more than **$100.00** cumulative, or make a silent paid call.
- Invent the contents of a missing/blocked source document.
- Auto-"repair" a legal fact (missing probate, chain gap, unsupported HBP,
  source/legal mismatch, ambiguous reservation). Those always escalate.

## Layout
```
scripts/validation_agent/
  app/            Streamlit dashboard
  config/         settings (caps clamped, secrets redacted)
  core/           orchestrator state machine + immutable run manager
  db/             append-only SQLite (schema + guarded client + logger)
  ingestion/      nondestructive workbook reader, classifier, manifest
  validators/     13 typed gates (Decimal/Fraction math)
  sources/        spend guard, OKCounty client, source finder, cache
  repair/         failure taxonomy, repair planner, safe XML editor
  recalc/         headless LibreOffice runner
  reports/        report finder, improver, output/export generator
  tools/          Windows setup/launchers + cross-platform healthcheck
  tests/          pytest suite (33 tests) proving the safety properties
  outputs/        versioned run folders (never overwritten)
```

## Setup (Windows)
1. `tools\setup_windows.bat` — detects Python 3.11+/3.12+ (installs via
   `winget install Python.Python.3.12` if missing), creates `.venv`, installs
   pinned deps, and creates `.env` from `.env.example`.
2. `tools\create_desktop_launcher.ps1` — puts **`DataBossX Validation Agent.bat`**
   on your Desktop (falls back to `tools\launch_dashboard.bat` if the Desktop
   is not writable).

## Setup (Linux/macOS/CI)
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python tools/healthcheck.py
python -m pytest tests -v
```

## Launch
- Dashboard: `tools\launch_dashboard.bat` (or `streamlit run app/dashboard.py`).
- Headless single run: `tools\run_agent.bat "C:\path\workbook.xlsx" "Prospect"`.

## Adding keys / live mode
Edit `.env` (never committed). To enable live source retrieval **all** must hold:
`DATABOSSX_DRY_RUN=false`, `DATABOSSX_LIVE_SOURCE_MODE=true`, and OKCounty
`USERNAME`/`PASSWORD`/`API_BASE_URL` set. Otherwise the agent stays in dry-run and
never hits the network.

## How the spend cap works
Every paid charge is authorized only if `cumulative + amount <= $100.00`, using
`Decimal`. The cumulative total is derived from the append-only `spend_ledger`,
so it survives restarts and cannot be silently reset. Paid retrieval also
requires `DATABOSSX_AUTO_APPROVE_PAID=true` and respects `PER_DOC_LIMIT_USD`.
Every allow/deny is logged.

## Certification vs escalation
- **CERTIFY**: every gate passed with zero escalations. A certified workbook copy
  is exported.
- **ESCALATE**: any FAIL/ESCALATE/ERROR remains (e.g., HBP unsupported, chain
  gap, missing source). An examiner packet + escalation matrix are exported.
- **MAX_ITERATIONS**: the ≤5 safe repair cycles were exhausted; outputs are still
  produced.

## Where exports appear
`outputs\validation_run_YYYYMMDD_HHMMSS\exports\` — markdown audit report, PDF
packet, JSON manifest, SQLite DB copy, source-verification packet,
missing-document list, escalation matrix, examiner ZIP (and a certified workbook
only when CERTIFY).

## Troubleshooting
- **LibreOffice missing** → recalc escalates cleanly; install it or set
  `LIBREOFFICE_PATH`.
- **Python missing** → run `setup_windows.bat`; if `winget` is unavailable it
  stops with a clear message.
- **Credentials absent** → agent runs in dry-run; source docs are queued/escalated.
- **Cross-platform**: set `DATABOSSX_AGENT_ROOT` / `DATABOSSX_ROOT` to override the
  Windows `D:\Desktop\DataBossX` defaults.

## Tests / fixtures
Fixtures are labeled `[FIXTURE]` and must never be used as verified legal facts.
Run `python -m pytest tests -v --cov=.`.
