# Roadmap — next best upgrades (priority order)

## P0 — Do now (security/correctness)
1. **Rotate all API keys** that were committed in `.env` files (see `RISKS.md`).
2. Add a `.git/hooks` or pre-commit secret scan (e.g. `gitleaks`/`detect-secrets`)
   so secrets can't be re-committed.

## P1 — High value, low risk
3. Add **authentication + rate limiting** to the FastAPI backend before any
   public exposure; remove `MOCK_AUTH` reliance.
4. Consolidate the three Python requirements files; remove duplicate/divergent
   pins (track in `MAJOR_UPGRADE_BACKLOG.md`).
5. Bump CI: `actions/setup-python@v3 → v5`, pin third-party actions by SHA, add a
   pip cache; install a lean dep set for the unit job.
6. Remove the no-op `deno.yml` workflow (or add real Deno code).
7. Add a `CODEOWNERS` file so workflow/dependency changes require review.

## P2 — Quality & reliability
8. Wire `automation/playwright_bot.py` to read `config/settings.toml` instead of
   hardcoded URL/workbook/sheet names.
9. Complete the LLM extraction in `automation/parsing.py` (currently regex stub).
10. Add a shared LLM client wrapper (timeouts, retries, redaction) used by
    backend + automation + doto.
11. Expand tests: doto `pull_list` normalization, `core/security` Fernet helpers,
    backend endpoints via FastAPI `TestClient`.
12. Add response/log redaction + a retention policy for stored LLM output.

## P3 — Nice to have
13. SBOM generation per ecosystem (cyclonedx/syft).
14. Replace mocked OCR in `backend/server.py` with real OCR, or clearly label the
    API as a demo.
15. Containerize each app with its own slim image; drop redundant python install
    in the final nginx stage of the `Dockerfile`.
