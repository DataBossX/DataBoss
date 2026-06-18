# DataBossX Troubleshooting

## `pip install` fails

- **`No matching distribution found for sqlite3`** — `sqlite3` is part of the
  Python standard library and must never appear in a requirements file. This was
  fixed in `backend/requirements.txt`; if you re-introduce it, remove it.
- **Build errors on `paddlepaddle` / `paddleocr`** — these are heavy, platform
  specific OCR deps. They are guarded with `sys_platform != 'win32'` in the root
  `requirements.txt`. On Windows or constrained environments, install only what
  you need (e.g. `pip install fastapi uvicorn aiosqlite loguru python-dotenv`).

## Backend won't start

- `ModuleNotFoundError` → `pip install -r requirements.txt`.
- LLM services show "unavailable" at `/api/health` → set the relevant API keys in
  `backend/.env`. The server still runs without them.
- CORS errors in the browser → set `CORS_ALLOW_ORIGINS` (comma-separated) in
  `backend/.env` to include your frontend origin, e.g. `http://localhost:3000`.
- `413 File too large` on upload → raise `MAX_UPLOAD_MB` in `backend/.env`.

## Frontend issues

- `yarn install` fails → ensure Node 20+; delete `node_modules` and retry.
- API calls 404/refused → check `REACT_APP_BACKEND_URL` in `frontend/.env` and
  that the backend is running on that URL.

## DOTO Image Commander

- "API key not configured" → set `OKCOUNTY_API_KEY` / `OPENAI_API_KEY` in
  `doto_image_commander/.env`, or enter them on the Settings page.
- Unexpected charges → the Queue page estimates cost; only **approved** items are
  downloaded. Review cost tracking in the app before bulk downloads.

## Automation bot

- Browser closes immediately → run `python -m playwright install chromium` first.
- Stuck on CAPTCHA → the browser is intentionally visible; solve it manually.
- `FileNotFoundError` for the workbook → place the `.xlsx` named in
  `config/settings.toml` in the working directory.

## Tests / lint

- `pytest` collects nothing → run from the repo root; suite lives in `tests/`.
- Backend helper tests are **skipped** → that's expected when backend runtime
  deps (fastapi/openai/...) aren't installed. Install them to run those tests.
- `flake8` complaints about line length → config is in `.flake8`
  (`max-line-length = 127`).

## Secrets accidentally committed

1. Stop and **rotate the exposed credentials** immediately at the provider.
2. Remove from tracking: `git rm --cached path/to/.env`.
3. Confirm `.gitignore` covers it (it now ignores `.env`, `*.db`, `logs/`).
4. Run `python scripts/security_scan.py` to verify nothing secret is tracked.
