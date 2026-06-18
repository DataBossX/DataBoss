# Baseline — state before upgrade

Captured on the upgrade branch before substantive changes. Environment: Linux
container, Python 3.11.15, Node v22.22.2, Yarn 1.22.22, pip 24.0.

| Command | Result | Notes |
|---------|--------|-------|
| `git status` | clean working tree | on working branch |
| `python3 --version` | 3.11.15 | OK (CI targets 3.10) |
| `node --version` | v22.22.2 | OK |
| `yarn --version` | 1.22.22 | OK |
| `python -c "import fastapi"` | **FAIL** | deps not installed in baseline env |
| `python -c "import pytest"` | **FAIL** | pytest not installed in baseline |
| `pip install -r backend/requirements.txt` | **WOULD FAIL** (pre-existing) | contained `sqlite3>=0.0.0` (stdlib; no such PyPI package) |
| `pytest` | n/a | no tests existed under a runnable suite; `backend_test.py` requires a live server |
| `flake8 . --select=E9,F63,F7,F82` | not run in baseline | tool absent |

## Pre-existing problems found (intel, not caused by this upgrade)

1. **`backend/requirements.txt` listed `sqlite3>=0.0.0`** — breaks `pip install`.
2. **Tracked secrets**: `backend/.env`, `frontend/.env` committed to git.
3. **Tracked artifacts**: `databossx.db`, `logs/databossx.log` committed.
4. **7 stray files** `backend/=0.7.0`, `=0.8.0`, `=0.20.0`, `=0.40.0`,
   `=1.54.0`, `=2.90`, `=10.0.0` — pip-redirect mistakes (`pip install x>=y`).
5. **`README.md`** was a one-line placeholder.
6. **`.gitignore`** did not ignore `.env`, `*.db`, or `logs/` (lines commented out).
7. **Backend CORS** `allow_origins=["*"]` with `allow_credentials=True`.
8. **Deprecated** `@app.on_event("startup")` in FastAPI.
9. **Dockerfile** printed env to build logs (`RUN cat /app/.env`) and used
   `rm /app/.env` (fails when absent).
10. **`automation/playwright_bot.py`** used bare `except:` and leaked file handles.
11. **`.github/workflows/deno.yml`** present but repo has no Deno code.

## Post-upgrade baseline (after fixes, same env)

| Command | Result |
|---------|--------|
| `pip install pytest flake8` | OK |
| `python -m pytest -q` | **12 passed** |
| `flake8 . --select=E9,F63,F7,F82` | **0 errors** |
| `python scripts/doctor.py` | 0 failures, 2 warnings (deps/.env not installed — expected) |
| `python scripts/security_scan.py` | hygiene scan clean; no secrets tracked |
| `python -m py_compile backend/server.py automation/playwright_bot.py scripts/*.py` | OK |
