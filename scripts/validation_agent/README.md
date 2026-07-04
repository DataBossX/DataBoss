# DataBossX Validation Agent

A high-integrity, automated title-validation, workbook-repair, source-retrieval,
report-improvement, and export system. The human examiner approves legal risk;
this software performs deterministic labor, validation, safe workbook repair,
append-only audit logging, and report generation.

## System laws (non-negotiable)

1. **Append-only integrity** — every durable write is an `INSERT`. UPDATE,
   DELETE, DROP, ALTER, REPLACE, INSERT OR REPLACE, UPSERT, VACUUM, ATTACH,
   DETACH and multi-statement SQL are blocked by a SQLite authorizer *and* by
   triggers (defense-in-depth against raw-sqlite bypass).
2. **Source-file immutability** — the original workbook is never opened for
   writing. Every change becomes a new `vNNN` version, SHA-256 hashed and
   audited. Reports/exports are versioned/timestamped, never overwritten.
3. **Legal-fact safety** — no title/legal/probate/ownership/lease/HBP fact is
   ever fabricated. Unverifiable facts route to `STATE_ESCALATE`.
4. **Economic enforcement** — all paid access goes through `sources/spend_guard.py`
   with a hard `$100.00` cap. Over-cap requests are blocked and escalated.
5. **Safe external access** — only lawful, authorized, configured access. No
   scraping or control circumvention. Missing credentials are logged, not
   hidden; all non-blocked work continues.
6. **Code quality** — strict typing, Pydantic/dataclasses, `Decimal`/`Fraction`
   for title math (no float comparisons), `lxml` for non-destructive XML edits.
7. **Tests** — every module has tests under `tests/`.
8. **Human escalation** — every escalation is an examiner-ready packet.

## Quick start (Windows)

```bat
tools\setup_windows.bat
tools\launch_dashboard.bat
```

To place a Desktop launcher:

```powershell
powershell -ExecutionPolicy Bypass -File tools\create_desktop_launcher.ps1
```

## Quick start (any platform)

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
python tools/healthcheck.py
python -m pytest tests -v
python -m core.cli path/to/workbook.xlsx     # headless run
python -m streamlit run app/dashboard.py     # dashboard
```

## Layout

```
config/      settings + caps + secret redaction
db/          schema.sql, append-only DatabaseManager, AuditLogger
core/        run_manager (immutable runs), orchestrator (state machine), cli
ingestion/   workbook_ingestor, sheet_classifier, manifest_builder
validators/  13 gates (workbook…certification), typed ValidationResult
sources/     spend_guard, source_finder, source_cache, okcounty_client
repair/      failure_classifier, repair_planner, xml_editor (lxml)
recalc/      libreoffice_runner (headless recalculation)
reports/     report_finder, report_improver, output_generator
app/         dashboard.py (Streamlit)
tools/       setup/launch/run/test scripts, healthcheck, desktop launcher
tests/       pytest suite + fixtures
outputs/     immutable run folders + build summaries + code backups
```

## State machine

`INIT → INGEST → VALIDATE → TRIAGE → EVALUATE_GATES → {REPAIR → RECALC →
ITERATE → VALIDATE} → CERTIFY | ESCALATE`

Iterations are hard-capped at 5. Only safe formula/math/format failures are
repaired; any legal/source/title/economic failure halts repair and escalates.

## Configuration

Copy `.env.example` to `.env`. Secrets are never printed or committed. Defaults:
dry-run **on**, live-source **off**, API cap **$100.00**, max iterations **5**.
