# Roadmap — next best upgrades (priority order)

## P0 — Do now (security/correctness)
1. **Rotate all API keys** that were committed in `.env` files (see `RISKS.md`).
2. ✅ **Done** — `.pre-commit-config.yaml` adds `detect-private-key`, a
   large-file guard, and a local secret/hygiene scan. Activate with
   `pip install pre-commit && pre-commit install`.

## P1 — High value, low risk
3. Add **authentication** to the FastAPI backend before any public exposure;
   remove `MOCK_AUTH` reliance. _(Rate limiting: ✅ done — sliding-window limiter
   on write endpoints.)_
4. Consolidate the three Python requirements files; remove duplicate/divergent
   pins (track in `MAJOR_UPGRADE_BACKLOG.md`).
5. ✅ **Done** — CI bumped to `setup-python@v5`, Python 3.11, pip cache, lean
   `requirements-dev.txt`, syntax gate + pytest. _(Still TODO: SHA-pin actions.)_
6. ✅ **Done** — removed the no-op `deno.yml` workflow.
7. ✅ **Done** — `.github/CODEOWNERS` added (set `@OWNER` to the real owner/team).

## P2 — Quality & reliability
8. ✅ **Done** — `automation/playwright_bot.py` now reads `config/settings.toml`
   via `automation/config.py`.
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
