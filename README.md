# DataBossX

DataBossX is a document-intelligence platform that ingests documents, runs OCR,
and analyzes the extracted text with multiple LLM providers. It ships with a
FastAPI backend, a React frontend, and several automation/analysis modules.

## Repository layout

| Path | Description |
| --- | --- |
| `backend/` | FastAPI API: document upload, OCR, LLM analysis, logging, analytics (`backend/server.py`). |
| `frontend/` | React app (Create React App + Tailwind) that talks to the backend API. |
| `automation/` | Playwright-based document automation bots and parsing/status helpers. |
| `doto_image_commander/` | Oklahoma county land-records automation app. |
| `mineral_deal_room/` | Mineral Deal Intelligence Room ("Target Factory") frontend. |
| `config/` | TOML configuration (`settings.toml`). |
| `prompts/` | Prompt templates for extraction and reasoning. |
| `tests/`, `backend_test.py` | Test suite. |

## Configuration

Secrets and environment-specific values are loaded from `.env` files and are
**never** committed.

1. Copy `backend/.env.example` to `backend/.env` and fill in real values
   (database URLs and LLM provider API keys).
2. The frontend reads `frontend/.env` (e.g. `REACT_APP_BACKEND_URL`).

Key backend environment variables:

- `SQLITE_DB_PATH` — path to the SQLite database (default `./databossx.db`).
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, … — enable each LLM
  provider; leave blank to disable.
- `CORS_ORIGINS` — comma-separated list of allowed frontend origins
  (default `http://localhost:3000`).

> ⚠️ If you previously cloned this repo, rotate any API keys that may have been
> committed to git history — removing a file from the repo does not invalidate a
> leaked credential.

## Running the backend

```bash
pip install -r requirements.txt
cd backend
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

The API is then available at `http://localhost:8001`. Key endpoints:

- `GET  /api/health` — service health and provider availability
- `POST /api/documents/upload` — upload a document for OCR + LLM processing
- `GET  /api/documents` — list documents
- `GET  /api/documents/{id}` — document details (OCR + analyses)
- `GET  /api/logs` — recent system logs
- `GET  /api/analytics` — aggregate metrics

## Running the frontend

```bash
cd frontend
yarn install
yarn start
```

## Tests

```bash
python -m pytest backend_test.py
```

(The backend must be running and reachable at the URL in `frontend/.env`.)
