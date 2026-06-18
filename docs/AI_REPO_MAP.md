# DataBossX — Repository Map

> Generated from repo inspection. Items marked _needs verification_ were
> inferred and not fully confirmed.

## Project purpose

DataBossX is a multi-app toolkit for **land / mineral document intelligence**
focused on Oklahoma and Colorado county records. It downloads/scrapes recorder
documents, runs OCR + LLM extraction, classifies ownership status, and presents
deal/pipeline dashboards.

## Languages, frameworks, runtimes

- **Python 3.10+** (CI uses 3.10; Docker backend uses 3.11): FastAPI, Streamlit,
  Playwright, pandas, SQLAlchemy/aiosqlite, OpenAI/Anthropic/Google LLM SDKs.
- **Node.js 20+ / Yarn**: React 19 (CRA) in `frontend/`, React 18 + Vite + TS in
  `mineral_deal_room/`.
- **Package managers**: pip (`requirements.txt`, `backend/requirements.txt`,
  `doto_image_commander/requirements.txt`), Yarn (frontend, mineral_deal_room).
- **Containers**: multi-stage `Dockerfile` (node build → python deps → nginx),
  `entrypoint.sh`, `nginx.conf`.

## Components & entry points

### `backend/` — FastAPI OCR + LLM API
- Entry: `backend/server.py` (`uvicorn server:app`, port 8001).
- Config: `backend/config.py` (typed `Settings.from_env`, validated at startup).
- Logging: `backend/logging_utils.py` (secret-redacting; loguru or stdlib).
- SQLite (`SQLITE_DB_PATH`, default `./databossx.db`); tables: documents,
  ocr_results, llm_analysis, system_logs.
- Endpoints: `GET /` (root), `/api/health`, `/api/documents` (+upload, +detail),
  `/api/logs`, `/api/analytics`.
- Cross-cutting middleware: per-request id (`X-Request-ID`), timing header,
  sliding-window rate limiter (429) on write methods, JSON error guard.
- Uploads: size-limited (`MAX_UPLOAD_MB`), extension allow-list
  (`ALLOWED_UPLOAD_EXTENSIONS`, 415 on reject), filename sanitization.
- **LLM SDK imports are optional** — the API starts even if openai/anthropic/
  google-generativeai are absent (reported "unavailable"). OCR is **mocked**
  (`PRIMARY_OCR = "demo_ocr"`).

### `frontend/` — OCR control center (CRA, React 19)
- Entry: `frontend/src/index.js` / `App.js`.
- Talks to backend via `REACT_APP_BACKEND_URL`. Tabs: Dashboard, OCR Control,
  Logs, Data/Analytics.

### `automation/` — Weld County recorder scraper
- Entry: `automation/playwright_bot.py` (`main()`), launched by `run.bat`.
- Loads owners from an Excel workbook, searches
  `https://weldrecorder.weldgov.com/web/`, extracts docs, classifies status via
  `status_logic.py`, writes results with `writer.py`.
- `parsing.py` is a partial LLM/regex extractor (LLM call is _stubbed_).
- Config in `config/settings.toml` (note: bot currently hardcodes URL/workbook;
  settings.toml is **not yet wired in** — _needs verification_).

### `doto_image_commander/` — Streamlit OK-county OCR workflow
- Entry: `doto_image_commander/app.py`, multipage (`pages/1_Import` … `6_Settings`).
- `api/okcounty.py` (paid downloads/search), `api/openai_client.py` (vision OCR).
- `core/`: `config.py`, `database.py` (SQLite, parameterized queries),
  `security.py` (Fernet key mgmt), `audit.py`. Has cost tracking.
- `run.sh` creates a venv and launches Streamlit on port 8501.

### `mineral_deal_room/` — Vite/React/TS dashboard
- Entry: `mineral_deal_room/src/main.tsx`, routes via React Router.
- Uses local `src/data/sampleData.ts`; **no backend calls** (demo data).

## Build / test / lint / run commands

| Action | Command |
|--------|---------|
| Doctor / health | `python scripts/doctor.py` |
| All tests/lint | `python scripts/test_all.py` |
| Unit tests | `pytest` |
| Lint (CI gate) | `flake8 . --select=E9,F63,F7,F82` |
| Security scan | `python scripts/security_scan.py` |
| Backend run | `cd backend && uvicorn server:app --reload --port 8001` |
| Frontend run | `cd frontend && yarn install && yarn start` |
| Mineral room run | `cd mineral_deal_room && yarn install && yarn dev` |
| DOTO commander | `cd doto_image_commander && ./run.sh` |
| Automation bot | `run.bat` (Windows) / `python -m automation.playwright_bot` |

## Important directories

- `backend/`, `frontend/`, `automation/`, `doto_image_commander/`,
  `mineral_deal_room/` — the five apps.
- `config/` — `settings.toml` for the automation bot.
- `prompts/` — extractor/reasoner prompt templates.
- `scripts/` — operator automation (doctor, tests, security, updates, backup).
- `tests/` — unit/smoke suite.
- `docs/` — this map, runbook, decisions, risks, roadmap, upgrade reports.
- `.devcontainer/`, `.emergent/` — cloud/devcontainer platform (Emergent) config.

## Config files

`requirements.txt`, `backend/requirements.txt`,
`doto_image_commander/requirements.txt`, `frontend/package.json`,
`mineral_deal_room/package.json`, `config/settings.toml`, `pytest.ini`,
`.flake8`, `.editorconfig`, `Dockerfile`, `nginx.conf`, `entrypoint.sh`,
`.github/workflows/*.yml`, `.github/dependabot.yml`.

## CI/CD workflows

- `.github/workflows/python-app.yml` — flake8 + pytest on push/PR to `main`
  (`permissions: contents: read`).
- `.github/workflows/deno.yml` — Deno lint/test. **No Deno source exists** in the
  repo; this workflow is effectively a no-op/legacy and a candidate for removal
  (see `docs/upgrade/CI_SECURITY.md`).

## Environment variables (names only)

- LLM: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`,
  `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`.
- Backend: `SQLITE_DB_PATH`, `CORS_ALLOW_ORIGINS`, `MAX_UPLOAD_MB`,
  `ALLOWED_UPLOAD_EXTENSIONS`, `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW_SEC`,
  `LOG_PATH`, `LOG_LEVEL`.
- Frontend: `REACT_APP_BACKEND_URL`.
- DOTO: `OKCOUNTY_API_KEY`, `OKCOUNTY_API_BASE_URL`, `OKCOUNTY_COST_PER_IMAGE`,
  `OKCOUNTY_COST_PER_SEARCH`, `DOWNLOADS_DIR`, `IMAGES_DIR`, `REPORTS_DIR`,
  `DB_PATH`, `AUDIT_LOG_PATH`, `ENCRYPTION_KEY`, `DOTO_KEY_FILE`.
- Platform/legacy: `SUPABASE_URL`, `SUPABASE_KEY`, `FRONTEND_URL`,
  `BACKEND_DOCKER_URL`, `MOCK_AUTH`, `FRONTEND_ENV` (Docker build arg).

## External services / integrations (names only)

OpenAI, Anthropic, Google Gemini, OKCountyRecords API, Weld County Recorder
website, Supabase (legacy), Emergent devcontainer platform.

## Risk areas / weak points

- **Secrets were committed** (`backend/.env`, `frontend/.env`) — now untracked
  and gitignored; **rotate any exposed keys** (see `docs/RISKS.md`).
- Backend OCR is mocked; not production document processing.
- `automation/parsing.py` LLM extraction is stubbed; relies on regex.
- No auth/rate limiting on the backend API; `MOCK_AUTH=true`.
- Multiple overlapping `requirements.txt` with duplicate/divergent pins.
- `databossx.db` and logs were committed — now untracked.

## Missing docs / tests / configs (addressed in this upgrade)

- README was a placeholder → rewritten.
- No runbook/troubleshooting/security docs → added under `docs/` + `SECURITY.md`.
- Minimal tests → added `tests/` unit + hygiene suite.
- No Dependabot/editorconfig/cursor rules → added.
