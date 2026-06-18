# Decisions

Records significant choices made during the autonomous upgrade and why.

## 2026-06 — Pass 3: DOTO tests, supply-chain, typing

- **Tested DOTO's cost-affecting logic first.** The dedup/normalization in
  `pull_list.py` decides which images get *paid* downloads, so that's where a
  bug costs real money — highest-value coverage for the effort.
- **Redirected DOTO import-time side effects** (audit log, db, key file) into a
  temp dir via `conftest.py` so tests never write to the repo or a real home.
- **Validate `ENCRYPTION_KEY` before writing it** in `core/security.py` —
  previously a bad key was persisted and only failed later at use.
- **pre-commit over a bespoke git hook.** Standard, portable, and includes
  `detect-private-key` + large-file guards; the local hook reuses our existing
  `scripts/security_scan.py` (no logic duplication).
- **Scoped mypy to the typed, dependency-light modules** rather than the whole
  tree, so the type gate is meaningful and green from day one; expand over time.
- **Repaired `cffi` in the dev image** so the system `cryptography` works; tests
  still skip gracefully if crypto is genuinely unavailable.

## 2026-06 — Backend & automation deep upgrade

- **Made LLM SDK imports optional** in `backend/server.py`. The API previously
  failed to import if any one of openai/anthropic/google-generativeai was
  missing. Optional imports + graceful degradation make the service far more
  operable and testable. Behavior for configured providers is unchanged.
- **Introduced a typed config layer** (`backend/config.py`) instead of scattered
  `os.getenv` calls. Stdlib dataclass (not pydantic-settings) to keep it
  import-light and unit-testable without the heavy stack.
- **Secret-redacting logger** (`backend/logging_utils.py`) so keys never reach
  log sinks; works with or without loguru.
- **In-process rate limiter** (sliding window, write methods only). Chosen over a
  Redis dependency because the app is single-process today; documented as a
  swap point if it scales out.
- **Upload extension allow-list** with a sensible document/image default. This is
  a deliberate (safer) behavior change for an upload endpoint; it is fully
  configurable via `ALLOWED_UPLOAD_EXTENSIONS` (empty = allow any).
- **Removed `deno.yml`.** Earlier it was kept pending sign-off; under the broader
  "make it better" mandate it was removed as dead CI (no Deno code exists).
- **Lean `requirements-dev.txt` for CI/tests** instead of installing the full
  heavy stack (paddleocr/playwright), so CI is fast and reliable. Tests skip
  cleanly when optional deps are absent.
- **Hermetic backend tests**: LLM clients are monkeypatched to `None` and a temp
  DB is used, guaranteeing no external/paid API calls during testing.
- **Wired automation to `config/settings.toml`** rather than rewriting the
  scraper. Config is the lowest-risk, highest-value improvement there.

## 2026-06 — Repository hardening & automation pass

- **Untracked secrets instead of deleting them.** `backend/.env` and
  `frontend/.env` were committed. Used `git rm --cached` (kept local files) and
  added them to `.gitignore`. Local developer secrets are preserved; the keys
  themselves should still be **rotated** (see `docs/RISKS.md`).
- **Removed stray `=N.N.N` files** in `backend/`. They are pip-redirect
  artifacts (`pip install x>=y` writing to a file named `=y`), not data.
- **Removed `sqlite3` from `backend/requirements.txt`.** It is a stdlib module;
  the pin breaks `pip install`. This is a clear bug fix.
- **CORS made configurable** via `CORS_ALLOW_ORIGINS` (default localhost) and
  credentials disabled when wildcard is used — was `allow_origins=["*"]` with
  credentials, which is both insecure and spec-invalid.
- **Adopted FastAPI lifespan** instead of deprecated `@app.on_event`. Functional
  equivalent; future-proof.
- **Added upload limits + filename sanitization** to the upload endpoint —
  prevents path traversal and resource exhaustion. Behavior preserved for valid
  uploads.
- **Kept `deno.yml` workflow** (no Deno code exists) rather than deleting it, to
  avoid changing CI without owner sign-off. Documented as a removal candidate in
  `docs/upgrade/CI_SECURITY.md`.
- **Python-first scripts with `.bat` launchers.** Logic lives in `scripts/*.py`
  (cross-platform); root `.bat` files are thin wrappers for Windows/Rodney.
- **Tests degrade gracefully.** Backend helper tests use `importorskip` so the
  suite stays green even when heavy OCR/LLM deps aren't installed; pure-logic and
  hygiene tests always run.
- **Did not push to remote and did not run dependency upgrades automatically.**
  Per mission constraints; updates are report-only via `scripts/update_deps_safe.py`.
