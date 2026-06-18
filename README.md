# DataBossX

DataBossX is a collection of land/mineral document-intelligence tools for
Oklahoma & Colorado county records. It bundles several independently runnable
apps that share LLM and OCR building blocks.

| Component | What it is | Stack | Entry point |
|-----------|------------|-------|-------------|
| `backend/` | Document OCR + multi-LLM analysis API | FastAPI + SQLite | `backend/server.py` |
| `frontend/` | OCR control center UI for the backend | React (CRA) | `frontend/src/index.js` |
| `automation/` | Weld County recorder scraper + status engine | Playwright + pandas | `automation/playwright_bot.py` |
| `doto_image_commander/` | OK county records download + OCR workflow | Streamlit + SQLite | `doto_image_commander/app.py` |
| `mineral_deal_room/` | Deal pipeline dashboard (demo data) | Vite + React + TS | `mineral_deal_room/src/main.tsx` |

> Full architecture, env vars, and risk notes: [`docs/AI_REPO_MAP.md`](docs/AI_REPO_MAP.md).
> How to run day-to-day: [`docs/RUNBOOK.md`](docs/RUNBOOK.md).
> When something breaks: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## Requirements

- Python 3.10+ (3.11 recommended)
- Node.js 20+ and Yarn (for `frontend/` and `mineral_deal_room/`)

## Quick start

```bash
# 0. Check your environment
python scripts/doctor.py            # or: RUN_DOCTOR.bat  (Windows)

# 1. Configure secrets (never commit these)
cp .env.example .env                # fill in OPENAI_API_KEY etc.
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 2. Backend API
pip install -r requirements.txt
cd backend && uvicorn server:app --reload --port 8001   # or RUN_APP.bat

# 3. Frontend (separate terminal)
cd frontend && yarn install && yarn start
```

## Common operator commands

| Task | Cross-platform | Windows |
|------|----------------|---------|
| Health check | `python scripts/doctor.py` | `RUN_DOCTOR.bat` |
| Run tests/lint | `python scripts/test_all.py` | `RUN_TESTS.bat` |
| Security scan | `python scripts/security_scan.py` | `SECURITY_SCAN.bat` |
| Check dep updates | `python scripts/update_deps_safe.py` | `SAFE_UPDATE.bat` |
| Local backup | `python scripts/backup_project.py` | — |
| Start backend | `cd backend && uvicorn server:app` | `RUN_APP.bat` |

## Security

Never commit real secrets. See [`SECURITY.md`](SECURITY.md). Secrets live in
`.env` files (gitignored); templates are the `*.env.example` files.

## Tests

```bash
pip install -r requirements.txt   # or at minimum: pip install pytest flake8
python scripts/test_all.py
```
