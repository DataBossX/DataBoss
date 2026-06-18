# Decisions

Records significant choices made during the autonomous upgrade and why.

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
