# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`DataBossX/DataBoss` is a **monorepo of loosely-coupled oil & gas / land-title data tools**, not a single application. Several independent sub-projects live side by side and are developed and run separately. There is no top-level build that ties them together — pick the sub-project you're working in and use its own commands.

Two cross-cutting rules govern all the title/report tooling (`grocery_report_pipeline.py`, `horizon/`, `automation/`) and must be preserved in any change:

- **Never fabricate title data.** Legal/ownership/lease/acreage/decimal/instrument facts that aren't supported by a source document are left blank and flagged (`REVIEW REQUIRED`, `Needs Examiner Review`, `ESCALATED`) — never guessed to make numbers tie out.
- **Zero destruction.** Sources are only read/copied, never deleted or overwritten. Duplicates are *planned* for quarantine and only *moved* (never deleted) when an explicit flag is passed; every generated report is a new versioned file.

Note: the title pipelines are designed to **run locally on the operator's machine where the source documents live** (e.g. `D:\DataBoss\...`, `D:\Desktop\Horizon`). The cloud checkout contains **no source documents**, so real reports can only be produced locally — in this environment, exercise them via their self-test / synthetic-corpus modes.

## Sub-projects

| Path | What it is | Stack |
| --- | --- | --- |
| `grocery_report_pipeline.py` | Flagship single-file, deterministic, rerunnable title-report pipeline. Stages **A–I**: inventory → text extraction → dedupe → classify → structured extraction → reconciliation/chain → validation → report assembly → dashboard. **Stdlib-first**: runs with zero third-party packages, degrading gracefully (CSV instead of XLSX, Markdown instead of DOCX). | Python stdlib + optional `openpyxl`/`python-docx`/`pdfplumber`/OCR |
| `horizon/` | "Horizon Command Center" — a modular, unit-tested package doing the same mission with **exact fraction interest math** (no floats), `Instrument_Number`-keyed OGL↔runsheet chaining, an autonomous Ingest→Validate→Repair→Evaluate loop (5-loop cap), and `_vNNN` versioning. Entry point `horizon/main.py`. | Python + `openpyxl`, `lxml` |
| `backend/` | `DataBossX API` — FastAPI service for document upload + OCR + multi-LLM (OpenAI/Anthropic/Gemini) analysis, persisting to SQLite via `aiosqlite`. Single file `server.py`, `/api/*` routes, serves on port **8001**. | FastAPI, aiosqlite, openai/anthropic/google-generativeai |
| `frontend/` | Create React App UI for the DataBossX API. | React 19, react-scripts, Tailwind, axios, yarn |
| `mineral_deal_room/` | Separate Vite + TypeScript React app (mineral deal-scoring dashboard, currently sample data). | Vite, React 18, TS, Tailwind |
| `doto_image_commander/` | Streamlit multi-page OCR/PDF app (Oklahoma county image puller). Entry `app.py`, launcher `run.sh`, serves on port **8501**. | Streamlit |
| `automation/` | Weld County recorder scraper helpers (`parsing.py`, `writer.py`, `status_logic.py`, `playwright_bot.py`) and the project-specific `roger_mills_title_report_builder.py`. Config in `config/settings.toml`. | Python, Playwright |

## Commands

### Python tests (CI runs the whole suite)
CI (`.github/workflows/python-app.yml`, Python 3.10) runs `flake8` then bare `pytest` from the repo root.

```bash
pytest                                             # full suite (grocery + all horizon tests)
pytest tests/test_grocery_pipeline.py -v           # grocery pipeline only
pytest tests/test_horizon_*.py -q                  # horizon only (~66 tests)
pytest tests/test_horizon_interest.py::<TestName>  # a single test
flake8 . --select=E9,F63,F7,F82 --show-source      # the lint gate that fails the build
```
`backend_test.py` is a **live integration test** that hits a running backend; it self-skips when no `BACKEND_URL`/`REACT_APP_BACKEND_URL` is set (the normal case in CI).

### grocery_report_pipeline.py
```bash
python grocery_report_pipeline.py --self-test                    # synthetic corpus, runs every stage — use this here
python grocery_report_pipeline.py --root "<docs-folder>"         # real run (local machine only)
python grocery_report_pipeline.py --root "<folder>" --apply-quarantine   # physically move byte-identical dupes
pip install -r requirements-grocery.txt                          # optional deps for full-fidelity XLSX/DOCX/PDF output
```
Outputs land in `./output/`. See `RUNBOOK.md` for the operator-facing procedure and `REPORT_PIPELINE_PLAN.md` for the stage-by-stage design.

### horizon/
```bash
pip install -r horizon/requirements.txt
python horizon/main.py --root "<docs-folder>"                    # full pipeline (local)
python horizon/main.py --root "<folder>" --build-from "<workbook.xlsx>"   # Intelligence Layer: OGL + Runsheet → tagged report
python horizon/main.py --root "<folder>" --dry-run               # scan + validate only, no writes
```
Windows operators use `Run_Horizon.bat`. Useful flags: `--section`, `--base`, `--max-loops N`, `--no-backup`. The Golden Source of validation truth is `project_notes_updated.xlsx` (falls back to a built-in canonical schema when absent).

### backend + frontend
```bash
# backend
pip install -r backend/requirements.txt
cd backend && uvicorn server:app --host 0.0.0.0 --port 8001

# frontend (uses yarn)
cd frontend && yarn install && yarn start        # dev; yarn build for production; yarn test
```
`Dockerfile` builds a combined image (React → nginx static, backend → uvicorn) started by `entrypoint.sh`. Env vars come from `.env` (see `.env.example`; `backend/` reads `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `SQLITE_DB_PATH`).

### other apps
```bash
cd doto_image_commander && ./run.sh              # Streamlit on :8501 (creates its own .venv)
cd mineral_deal_room && npm install && npm run dev
```

## Architecture notes

- **The two title pipelines (`grocery_report_pipeline.py` and `horizon/`) are the substance of this repo.** They solve overlapping missions differently: grocery is a monolithic stdlib-first script optimized for graceful degradation on any machine; horizon is a decomposed, heavily-tested package (`foundation`/`interest`/`chaining`/`pipeline`/`orchestrator`/`repair`/`validation`/`versioning`) optimized for exact-fraction correctness and a repair loop. When changing behavior, know which one you're in — they do not share code.
- **`horizon/main.py` supports both `python horizon/main.py` and `python -m horizon.main`** via a `__package__` guard that fixes up `sys.path`; keep imports working under both.
- **Interest math in horizon uses `fractions.Fraction`/Decimal, never floats** (`Grantor − Conveyed = Retained`). Do not introduce float arithmetic into interest/decimal reconciliation.
- **`backend/server.py` is intentionally a single-file FastAPI app** with wide-open CORS and multi-provider LLM clients initialized lazily (only if the corresponding API key is present). SQLite path is env-configurable; a `databossx.db` checked into the root is demo/dev state.
- **Root-level Markdown files (`PROJECT_STATUS.md`, `TODO_NOW.md`, `QA_CHECKLIST.md`, `RUNBOOK.md`, `REPORT_PIPELINE_PLAN.md`) are the living project record** for the grocery-report effort — consult them before changing pipeline behavior, and keep them in sync when you do.
- `README.md` is a stub; there are no Cursor or Copilot rule files.
