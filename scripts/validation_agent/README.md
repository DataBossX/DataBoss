# DataBossX — Automated Validation, Repair, Source Retrieval & Escalation Agent

A safety-first assistant for oil-&-gas title workbooks. The **human owns all
legal judgment.** The software performs labor: evidence collection, math,
validation, safe workbook-defect repair, report generation, and escalation
packaging. It **never** fabricates legal, title, probate, source, lease,
ownership, or well/HBP facts, and it **never** overwrites a source file.

---

## What this system will NEVER do

1. Fabricate legal/title/probate facts, parties, legal descriptions, book/page
   or instrument references, or well/HBP support.
2. Overwrite source workbooks, PDFs, images, prior reports, the audit DB, or
   any prior version. All outputs are versioned and append-only.
3. Make a silent paid API call. Every paid call is gated and logged.
4. Exceed the **$100.00** cumulative spend cap (mathematically enforced with
   `Decimal`, hard-clamped even if the environment asks for more).
5. Auto-repair anything requiring legal inference (missing probate, ambiguous
   reservation, grantor not vested, source contradiction, unsupported HBP…).
   Those are **escalated** to the human examiner.

Only **safe** defects are auto-repaired: formula defects where the exact
intended formula is known from an adjacent cell, template, or immutable prior
version.

---

## Layout

```
scripts/validation_agent/
  app/dashboard.py          Streamlit control panel
  config/settings.py        paths, caps, modes (secret-redacting dumps)
  core/                     orchestrator state machine + immutable run manager
  db/                       append-only SQLite (schema + guarded client + audit)
  ingestion/                non-destructive workbook read + classification
  validators/               13 typed validation gates
  sources/                  spend guard, OKCounty client, source finder, cache
  repair/                   failure taxonomy, repair planner, safe XML editor
  recalc/                   headless LibreOffice recalculation
  reports/                  report finder/improver + examiner export bundle
  tools/                    Windows setup/launchers + healthcheck + CLI
  tests/                    pytest suite (fixtures are clearly synthetic)
  outputs/                  versioned run folders + audit DB (git-ignored)
```

---

## Setup (Windows)

```bat
cd D:\Desktop\DataBossX\scripts\validation_agent
tools\setup_windows.bat
```

This detects Python 3.11+/3.12+ (installing via `winget install Python.Python.3.12`
if missing), creates `.venv`, installs **pinned** dependencies, copies
`.env.example` → `.env`, validates imports, and runs the healthcheck. If Python
cannot be installed automatically it stops with a clear message.

## Setup (Linux/macOS, e.g. CI)

```bash
cd scripts/validation_agent
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python tools/healthcheck.py
```

Paths auto-resolve relative to the module when the Windows defaults are absent.

---

## Launch

- **Dashboard:** `tools\launch_dashboard.bat` (activates `.venv`, loads `.env`,
  runs healthcheck, starts Streamlit at http://localhost:8501, opens a browser).
- **Desktop launcher:** `powershell -ExecutionPolicy Bypass -File tools\create_desktop_launcher.ps1`
  creates `Desktop\DataBossX Validation Agent.bat` (and a `.lnk` if possible).
  The Desktop `.bat` is the *only* file placed outside the module folder.
- **One-shot CLI:** `tools\run_agent.bat "C:\path\to\workbook.xlsx"`

---

## Adding keys

Edit `.env` (never commit it). Secrets are read from the environment only and
are always redacted in config dumps and logs.

```
OKCOUNTY_USERNAME=...
OKCOUNTY_PASSWORD=...
OKCOUNTY_API_BASE_URL=https://...
LIBREOFFICE_PATH=C:\Program Files\LibreOffice\program\soffice.exe
```

---

## Dry-run vs live source mode

- **Dry-run (default):** no paid calls, no external retrieval. `DATABOSSX_DRY_RUN=true`.
- **Live mode:** set `DATABOSSX_DRY_RUN=false` **and** `DATABOSSX_LIVE_SOURCE=true`
  **and** provide OKCounty credentials. Live mode may search official APIs,
  retrieve free metadata/documents, queue paid documents, and retrieve paid
  documents **only** if the spend guard and approval policy allow.

Paid retrieval requires either interactive examiner approval or
`DATABOSSX_AUTO_APPROVE_PAID=true` with a per-document limit
(`DATABOSSX_PER_DOC_LIMIT_USD`). Either way, cumulative spend can never exceed
**$100.00**.

---

## How the spend cap works

Every prospective paid call goes through `SpendGuard.authorize()`, which uses
`Decimal` math to check `cumulative + amount <= cap`. Approved spend advances a
cumulative total that is also persisted to the append-only `spend_ledger`.
Blocked attempts are recorded too (failed/blocked retrieval is never hidden).
The cap is clamped to the absolute ceiling of $100.00 regardless of config.

---

## Certification vs escalation

- **CERTIFIED** — every gate passed; a certified workbook copy is exported.
- **ESCALATED** — one or more gates failed/escalated (unsafe to auto-resolve);
  an escalation matrix and examiner packet are produced.
- **MAX_ITERATIONS** — safe repairs kept being applied but blocking issues
  remained after the iteration cap; treated as escalation.

A full export bundle is produced in **every** case.

---

## Where exports appear

```
outputs\validation_run_YYYYMMDD_HHMMSS\exports\
```

Includes: markdown audit report, PDF packet, JSON manifest, DB snapshot, source
verification packet, missing-document list, escalation matrix, certified and/or
repaired workbook copies, and a zipped examiner package. Nothing is overwritten;
colliding names are numbered.

---

## Tests

```bat
tools\run_tests.bat
```
or
```bash
python -m pytest tests -v --cov=.
```

The suite proves: append-only DB (UPDATE/DELETE blocked incl. raw-connection
bypass), spend cap enforcement, non-destructive ingestion, validator math
(acreage 637.42, exact interest conservation, chain vesting), safe XML editing
with drawing/media preservation, orchestrator iteration bounding, and that the
source finder / report improver never fabricate facts.

---

## Roger Mills report finalizer

Finalize title reports across multiple source folders into your template format:

```bat
python tools\rogermills_finalize.py ^
    --horizon "D:\Desktop\Horizon" ^
    --output  "D:\Desktop\Horizon\rogermillsfinalreports" ^
    --template "D:\Desktop\Horizon\Roger Mills\Template(30).xlsx"
```

It reads the `.env` at the Horizon root (API key / OKCounty creds — never
printed), inventories and **timestamp-backs-up** every workbook in
`Roger Mills`, `Roger Mills 2`, `Roger Mills 3`, runs a **tournament + loops**
to pick the best base per folder, and writes one **template-formatted** final
per folder into the output folder (versioned, never overwriting). Rules:

- **Tract sheet = scope.** The output never adds a tract that isn't on the
  tract sheet ("don't go off the tract sheets"); footing/format are fixed,
  legal facts are never invented.
- **Title sheet data** (section, county, dates) is normalized into the
  template's title block.
- **OGL numbers** are taken from the OGL sheet and reconciled onto each tract.
- Anything missing/ambiguous (a blank legal, a tract with no OGL number) is
  written to a `REVIEW_*.md` file for the examiner — **never fabricated**.
- Any paid source retrieval is gated by the $100 spend guard; nothing is spent
  silently.

Run with `--dry-run` first to see the tournament plan without writing anything.
Override sheet detection with `--tract-sheet`, `--title-sheet`, `--ogl-sheet`
if your tabs are named unusually.

## Troubleshooting

- **Python not found:** install 3.12 from python.org, re-run setup.
- **LibreOffice missing/broken:** recalculation is skipped and logged honestly
  (the run still completes); set `LIBREOFFICE_PATH` or install LibreOffice to
  enable it.
- **Live mode does nothing:** confirm `DATABOSSX_DRY_RUN=false`,
  `DATABOSSX_LIVE_SOURCE=true`, and OKCounty credentials are set.
- **Permission denied on Desktop launcher:** run the PowerShell script from an
  elevated shell, or use `tools\launch_dashboard.bat` directly.
- **Import errors:** ensure the `.venv` is activated; run `tools\healthcheck.py`.
