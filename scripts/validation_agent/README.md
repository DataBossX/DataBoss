# DataBossX Automated Validation, Repair, Source-Retrieval, Report-Improvement & Export Agent

Labor-automation for cursory mineral-title workbooks. The **human owns all legal
judgment.** The software does the labor: validation math, evidence collection,
append-only auditing, *safe* workbook repair (formulas only), source-document
queueing, report improvement, and examiner-ready packaging. It **never**
fabricates title facts and it **escalates** anything that requires a legal call.

Module root: `scripts/validation_agent/` (maps to
`D:\Desktop\DataBossX\scripts\validation_agent` on the Windows target). Paths are
resolved from `DATABOSSX_AGENT_ROOT` when set, otherwise from the module
location — so the same code runs on Windows and on Linux/CI unchanged.

---

## 1. Setup (Windows)

```bat
tools\setup_windows.bat
```

This detects Python 3.11+/3.12+ (installing via `winget install Python.Python.3.12`
if missing), creates `.venv`, installs the **pinned** dependencies, generates
`.env` from `.env.example`, and validates imports. If winget is unavailable it
stops with a clear message.

### Setup (Linux/macOS, for dev/CI)
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
```

## 2. Launch

```bat
tools\launch_dashboard.bat        REM healthcheck + Streamlit dashboard
tools\run_agent.bat "C:\path\to\workbook.xlsx"   REM one run, headless
tools\run_tests.bat               REM pytest + coverage
tools\create_desktop_launcher.ps1 REM writes "DataBossX Validation Agent.bat" to the Desktop
tools\build_final_reports.bat     REM batch tournament: Horizon folders -> rogermillsfinalreports
```

### Batch tournament builder (multiple folders → final reports)

`tools\build_final_reports.bat` (or the CLI below) scans one or more source
folders, finds the best report in each, runs a **tournament** of OGL/title
reconciliation strategies, and writes the winning final report (template naming)
plus a per-folder reconciliation note into an output folder. It:

* fills blank **OGL No. / Royalty / Expiration** on Title owner rows by matching
  the owner to the **OGL register grantor** (tract-coverage aware), **verifying**
  existing values instead of overwriting them and **flagging conflicts**;
* converts hard-coded tract totals to `SUM` formulas;
* **does not alter tract legal descriptions** ("don't go off the tract sheets");
* reports unmatched owners for examiner review and **never invents** lease data.

```bat
python tools\build_final_reports.py ^
  --input "D:\Desktop\Horizon\Roger Mills" ^
  --input "D:\Desktop\Horizon\Roger Mills 2" ^
  --input "D:\Desktop\Horizon\Roger Mills 3" ^
  --out   "D:\Desktop\Horizon\rogermillsfinalreports" ^
  --env   "D:\Desktop\Horizon\.env"
```

Sources are never overwritten; each final report is a new file.

Dashboard: `streamlit run app/dashboard.py`. CLI:
`python tools/run_agent_cli.py <workbook.xlsx>`.

## 3. Adding keys

Edit `.env` (created from `.env.example`). Secrets live **only** in `.env`,
never in source, and are never printed (config dumps show `***REDACTED***`).
Leave `OKCOUNTY_*` blank to remain in dry-run.

## 4. Dry-run vs. live source mode

* **Dry-run (default):** no network calls, no spend. Missing sources are
  queued and escalated. This is safe to run anytime.
* **Live mode:** set `DATABOSSX_DRY_RUN=false` **and** `DATABOSSX_LIVE_SOURCE=true`
  **and** provide OKCounty credentials. Live mode may search official APIs,
  retrieve free metadata/documents, queue paid documents, and retrieve paid
  documents only if the spend guard and the approval policy allow.

## 5. How the spend cap works

* Hard ceiling is **exactly $100.00** and is enforced with `Decimal` math against
  the append-only `spend_ledger`. A configured cap larger than $100 is clamped.
* Every estimate, charge, and **block** is written to `spend_ledger` + `api_calls`.
* Paid retrievals require explicit approval unless `DATABOSSX_AUTO_APPROVE_PAID=true`
  and the per-document cost is within `DATABOSSX_PER_DOCUMENT_LIMIT_USD`. Even
  then, cumulative spend can never exceed $100.00.

## 6. What the system will NEVER do

* Fabricate legal/title/probate/lease/ownership facts, parties, legal
  descriptions, book/page, instrument numbers, or well/HBP support.
* Overwrite a source workbook, PDF, image, prior report, or the audit DB.
* Make a silent paid API call, or exceed the $100.00 cap.
* Auto-repair anything legal — missing probate, unverified vesting, ambiguous
  reservations, unsupported HBP, source/legal mismatch, or chain gaps all
  escalate to the human examiner.

Only **formula defects with a knowable intended formula** (e.g. a tract total
that should be a `SUM` over its owner rows) are auto-repaired, and only on a
fresh copied workbook version.

## 7. Certification vs. escalation

* **CERTIFY** — every gate passed; a `CERTIFIED_*.xlsx` is emitted.
* **ESCALATE** — open failures/escalations remain; an escalation matrix +
  packet are emitted and the human decides. (This is the normal outcome for a
  real cursory workbook with title gaps.)
* **MAX_ITERATIONS** — the ≤5 repair loop was exhausted; outputs are still
  produced. The loop cannot run forever.

## 8. Where exports appear

```
outputs\validation_run_YYYYMMDD_HHMMSS\
    input\  versions\  sources\  reports\  audit\  logs\  escalations\  exports\
```
`exports\` holds the markdown audit report, PDF packet, JSON manifest, a copy of
the audit DB, the missing-document list, the escalation matrix, the improved
report, the repaired/certified workbook, and `examiner_package.zip`.

## 9. Architecture

```
config/      settings + hard caps
db/          append-only SQLite (triggers + authorizer), audit logger
core/        run_manager (immutable versions), orchestrator (state machine)
ingestion/   nondestructive read, manifest, sheet classifier
validators/  13 gates (integrity, acreage, interest, chain, instrument,
             OGL/WI, formula, sources, well/HBP, audit, final cert)
repair/      failure taxonomy, planner, safe lxml XML editor
recalc/      headless LibreOffice runner
sources/     spend guard, OKCounty client, source finder + cache
reports/     report finder, improver, output generator
app/         Streamlit dashboard
tools/       Windows setup/launchers, healthcheck, CLI
tests/       pytest suite + synthetic fixtures
```

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `winget` missing | Install Python 3.12 from python.org, re-run setup. |
| LibreOffice not found | Install it or set `LIBREOFFICE_PATH`; recalc escalates cleanly meanwhile. |
| “Paid retrieval requires approval” | Expected — approve explicitly or set the auto-approve policy. |
| Dashboard import error | Run `tools\setup_windows.bat` to (re)build `.venv`. |
| Everything ESCALATES | Normal for a workbook with real title gaps — read the escalation matrix. |

> Test fixtures under `tests/fixtures/` are **synthetic** and must never be
> treated as verified source facts.
