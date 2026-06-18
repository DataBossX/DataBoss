# AI Changelog

Entries by autonomous agent sessions. Newest first.

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
