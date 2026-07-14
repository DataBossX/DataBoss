# AGENTS.md

## Cursor Cloud specific instructions

This repo is a **collection of mostly-independent tools** (not one integrated app). The startup
update script already installs Python deps (curated pip list), `frontend` node modules (yarn), and
the sibling `databossx-site` node modules. Services are NOT auto-started — start what you need.

### Services / how to run (dev)

| Component | Run (dev) | Port | Notes |
| --- | --- | --- | --- |
| `backend` (FastAPI demo) | `cd backend && python3 -m uvicorn server:app --host 0.0.0.0 --port 8001` | 8001 | API is under `/api/*` (e.g. `/api/health`); `/` returns 404. Uses local SQLite (`backend/databossx.db`, auto-created). No external DB. |
| `frontend` (React CRA) | `cd frontend && BROWSER=none yarn start` | 3000 | Needs `backend` running. Copy `frontend/.env.example` -> `frontend/.env` (`REACT_APP_BACKEND_URL=http://localhost:8001`). |
| `horizon` (CLI) | `python3 -m horizon --help` / `--dry-run` | n/a | Pure Python; operates on local Excel files. |
| `grocery_report_pipeline.py` | `python3 grocery_report_pipeline.py --self-test` | n/a | Generates a synthetic corpus + all outputs into gitignored `output/`. |
| `doto_image_commander` (Streamlit, optional) | `cd doto_image_commander && streamlit run app.py --server.port 8501` | 8501 | Runs without keys; live pulls/AI need `OKCOUNTY_API_KEY` / `OPENAI_API_KEY`. |
| `mineral_deal_room` (Vite, optional) | `cd mineral_deal_room && npm install && npm run dev` | 5173 | Standalone client-only prototype. |

### Non-obvious gotchas

- **`backend/requirements.txt` is partly broken/heavy:** it lists `sqlite3>=0.0.0` (stdlib, not a
  PyPI package — breaks `pip install -r`) and `paddleocr`/`paddlepaddle` (huge, and NOT imported —
  OCR in `server.py` is mocked). The update script therefore installs a **curated subset** instead
  of that file. If you need to add a backend dep, install it directly; don't run the raw file.
- LLM keys are optional. Without `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`GEMINI_API_KEY`, `/api/health`
  reports those services `unavailable` and uploads still fully process (mock OCR, no LLM analysis).
- Python packages install to the **user site** (`pip install --user`); no venv is used.

### Tests & lint

- Unit/integration suite: `python3 -m pytest -q` from repo root (the 7 `backend_test.py` cases are
  live-integration and are **skipped** unless a backend URL is set).
- Backend integration against a running server: `BACKEND_URL=http://localhost:8001 python3 backend_test.py`.
- Lint (matches CI `.github/workflows/python-app.yml`):
  `python3 -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`.
