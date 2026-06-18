# Security Policy

## Reporting a vulnerability

If you discover a security issue, **do not open a public issue**. Contact the
maintainer (Rodney) directly and privately with:
- a description of the issue and its impact,
- steps to reproduce,
- any suggested remediation.

Please allow reasonable time for a fix before any public disclosure.

## Secret handling

- **Never commit secrets.** Real values live only in `.env` files, which are
  gitignored. Commit only the `*.env.example` templates (placeholders only).
- API keys in use: OpenAI, Anthropic, Google Gemini, OKCountyRecords. Store them
  in the appropriate `.env` (root, `backend/`, `frontend/`, or
  `doto_image_commander/`).
- If a secret is ever committed:
  1. **Rotate it immediately** at the provider — assume it is compromised.
  2. `git rm --cached <file>` and confirm `.gitignore` covers it.
  3. Run `python scripts/security_scan.py`.
- Run the secret/hygiene scan regularly: `python scripts/security_scan.py`
  (or `SECURITY_SCAN.bat`). Optionally install `pip-audit` for dependency CVEs.
- The DOTO encryption key (`master.key`, `.doto_commander/`) and any `*.key` /
  `*.pem` files are gitignored — never share or commit them.

## Secure defaults in this repo

- Backend CORS is configured via `CORS_ALLOW_ORIGINS` (no wildcard-with-
  credentials); defaults to localhost.
- Upload size is bounded by `MAX_UPLOAD_MB`; empty uploads are rejected.
- Uploaded filenames are sanitized to prevent path traversal.
- The Dockerfile no longer prints env to build logs.

## Known limitations (see `docs/RISKS.md`)

- The backend API has **no authentication or rate limiting** yet (`MOCK_AUTH`).
- Backend OCR is mocked; LLM responses are stored in SQLite without redaction.

## Dependencies & supply chain

- Dependency updates are proposed via Dependabot (`.github/dependabot.yml`),
  with security updates separated from routine version bumps.
- Use `python scripts/update_deps_safe.py` to review outdated packages; record
  major upgrades in `docs/upgrade/MAJOR_UPGRADE_BACKLOG.md`.
