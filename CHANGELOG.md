# Changelog

## v2.1.0 — security, frontend wiring, hardening, tooling

### Security posture (opt-in, backward compatible)
- API-key auth (`X-API-Key`) on data endpoints — active only when `API_KEYS`
  is configured; `/api/health` and `/metrics` stay open.
- In-process per-client rate limiting (`RATE_LIMIT_PER_MINUTE`, returns 429 +
  `Retry-After`).
- Security response headers (`X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`) always applied. Shared `ApiError` envelope across layers.

### Frontend wiring
- Centralized API client (`frontend/src/api.js`): base URL, optional
  `REACT_APP_API_KEY` header, and real error parsing.
- Upload errors now show the backend's reason (too large / unsupported /
  rate-limited); accepted file types aligned to what the backend supports.
- Dashboard shows live Text-OCR and Image-OCR availability; document detail
  shows the OCR engine. Verified with a production `yarn build`.

### Backend
- New `ocr_engine` column (with an additive migration) surfaced through the API.

### Other modules hardened
- `automation/status_logic.py`: guards for missing owner/empty docs.
- `automation/playwright_bot.py`: replaced bare `except:` with `except Exception:`.

### Test depth + tooling
- Unit tests for `ocr` and `llm` (retry/timeout/availability) and for the
  `automation` logic. Suite now 47 tests; `pytest.ini` covers both dirs.
- Added `ruff` + `mypy` config (`pyproject.toml`), a `.pre-commit-config.yaml`,
  and wired ruff + mypy into CI alongside pytest.

## Backend v2.0.0 — substantial quality overhaul

### Real OCR + robustness
- Replaced the mock OCR (`PRIMARY_OCR = "demo_ocr"`) with real extraction:
  text files are decoded directly; images are run through Tesseract
  (`pytesseract`) with graceful degradation when the engine is unavailable.
- Added upload validation: empty files (400), oversized files (413, via
  `MAX_UPLOAD_BYTES`), and unsupported types (415).
- Replaced per-operation SQLite connections with a single shared `aiosqlite`
  connection (WAL mode) and added indexes on the columns the API queries.

### Offline test suite + CI
- Added `backend/tests/test_api.py` (11 tests) using FastAPI's `TestClient` —
  no live server, no hard-coded `/app` paths. Scoped via root `pytest.ini`.
- Reworked the GitHub Actions workflow to install a focused dependency set and
  run flake8 + pytest on push/PR.

### Reliability hardening
- LLM calls now run with a per-call timeout and exponential-backoff retries;
  a failing/unavailable provider degrades gracefully instead of failing the
  whole document.
- Provider SDKs (`openai`, `anthropic`, `google-generativeai`) are imported
  lazily, so the backend runs even when a SDK is missing.
- Consistent JSON error envelope (`{"error": ...}`) via exception handlers.

### Observability
- Structured (JSON) logging via loguru.
- Request-timing middleware records per-request metrics and an
  `X-Process-Time-ms` header.
- New `/api/metrics` (JSON) and `/metrics` (Prometheus text) endpoints, plus
  domain counters (uploads, OCR, LLM outcomes).

### Packaging / build fixes
- `backend/requirements.txt`: removed the bogus `sqlite3` pin (stdlib) and the
  unused heavy `paddlepaddle`/`paddleocr`/`pyttsx3` deps; added `pytesseract`.
- `Dockerfile`: `rm -f /app/.env` (the previous `rm` broke the build now that
  `.env` is untracked) and installed the `tesseract-ocr` engine.

### Refactor
- Split the monolithic `server.py` into focused modules: `config`, `db`,
  `ocr`, `llm`, `observability`. API request/response shapes are unchanged.
