# AI Changelog

Entries by autonomous agent sessions. Newest first.

## 2026-06-18 — Pass 3: DOTO coverage, supply-chain guards, static typing

### DOTO Image Commander (`doto_image_commander/`)
- First tests for this paid-API app: `test_doto_config`, `test_doto_security`
  (Fernet round-trip, restrictive key perms, key derivation), and
  `test_doto_pull_list` (cost-affecting normalization + dedup logic).
- `core/security.py`: validate a supplied `ENCRYPTION_KEY` before persisting it
  (fail loudly on an invalid key instead of writing garbage to disk).

### Supply-chain / prevention
- `.pre-commit-config.yaml`: trailing-whitespace, EOF, YAML/TOML/JSON checks,
  **detect-private-key**, large-file guard, flake8 syntax gate, and a local
  hook running `scripts/security_scan.py`.
- `.github/CODEOWNERS`: owner review required on workflows, dependency
  manifests, and security/config files (fill in `@OWNER`).

### Static typing
- `mypy.ini` + `mypy` step in `test_all.py` and CI for the typed modules
  (`backend/config.py`, `backend/logging_utils.py`, `automation/config.py`).

### Tests: 56 → 72, all passing. CI now runs flake8 + mypy + pytest.

## 2026-06-18 — Backend & automation deep upgrade ("10,000x" pass)

### Backend architecture (`backend/`)
- New `config.py`: typed, validated `Settings` loaded from env (single source of
  truth for DB path, CORS, upload limits, allowed extensions, rate limits,
  logging, provider keys). Stdlib-only, unit-tested.
- New `logging_utils.py`: secret-redacting logger (masks OpenAI/Anthropic/Google/
  AWS/bearer tokens), prefers loguru, falls back to stdlib. Unit-tested.
- `server.py` refactor (behavior-preserving + hardening):
  - **Optional LLM imports** — API now starts even if `openai`/`anthropic`/
    `google-generativeai` are not installed (graceful "unavailable").
  - Config-driven settings; lazy/defensive LLM client init.
  - HTTP middleware: per-request id (`X-Request-ID`), timing header, and a
    sliding-window **rate limiter** (429) on write methods.
  - Upload **extension allow-list** (415) + cross-platform filename
    sanitization (handles Windows `\` paths).
  - New `GET /` root; `/api/health` now reports limits and version.
  - Global exception guard returns JSON, never leaks stack traces.

### Automation (`automation/`)
- New `config.py`: loads `config/settings.toml` (stdlib `tomllib`) into a typed
  `AutomationConfig` with safe fallbacks.
- `playwright_bot.py` now reads URL/workbook/sheets/delay/output path from config
  instead of hardcoded constants.

### Tests (12 → 56, all passing)
- `test_config`, `test_logging_redaction`, `test_backend_api` (hermetic
  TestClient — no external calls), `test_automation_config`, `test_parsing`.

### CI / tooling
- Rewrote `python-app.yml`: `setup-python@v5`, Python 3.11, pip cache, installs
  lean `requirements-dev.txt`, syntax gate + full pytest.
- Removed no-op `deno.yml` (no Deno source exists).
- Added `requirements-dev.txt` and a `Makefile` (`make help`).


## 2026-06-18 — Repository upgrade, hardening & automation

### Security
- Untracked committed secrets `backend/.env`, `frontend/.env` (kept locally,
  gitignored). **Owner must rotate exposed keys.**
- Untracked `databossx.db` and `logs/databossx.log`; expanded `.gitignore` to
  cover `.env*`, `*.db`, `logs/`, caches, build output, backups.
- Backend CORS made configurable (`CORS_ALLOW_ORIGINS`), no wildcard+credentials.
- Added upload size limit (`MAX_UPLOAD_MB`) + filename sanitization (path
  traversal) to `/api/documents/upload`.
- Dockerfile no longer prints env to build logs; `rm -f` for absent `.env`.
- Added `SECURITY.md`, `.cursorignore`, `.cursorindexingignore`,
  `.github/dependabot.yml`, `docs/upgrade/CI_SECURITY.md`.

### Bug fixes
- Removed stdlib `sqlite3>=0.0.0` from `backend/requirements.txt` (broke pip).
- Removed 7 stray `backend/=N.N.N` pip-redirect artifact files.
- Replaced bare `except:` and leaked file handles in `automation/playwright_bot.py`.
- Migrated backend off deprecated `@app.on_event` to lifespan handler.

### Automation & tooling
- Added `scripts/`: `doctor.py`, `test_all.py`, `security_scan.py`,
  `update_deps_safe.py`, `backup_project.py`.
- Added Windows launchers: `RUN_DOCTOR/RUN_TESTS/RUN_APP/SAFE_UPDATE/SECURITY_SCAN.bat`.
- Added `pytest.ini`, `.flake8`, `.editorconfig`.

### Tests
- New `tests/`: `test_status_logic.py`, `test_repo_hygiene.py`,
  `test_backend_helpers.py` (+ `conftest.py`). 12 passing.

### Docs & AI setup
- Rewrote `README.md`; added `docs/AI_REPO_MAP.md`, `RUNBOOK.md`,
  `TROUBLESHOOTING.md`, `DECISIONS.md`, `RISKS.md`, `ROADMAP.md`,
  `CHANGELOG_AI.md`, `docs/upgrade/{BASELINE,UPGRADE_REPORT,MAJOR_UPGRADE_BACKLOG,CI_SECURITY}.md`.
- Added `.cursor/rules/*.mdc`, `.cursor/BUGBOT.md`, `AGENTS.md`.
