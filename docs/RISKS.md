# Risks

| # | Risk | Severity | Status / Mitigation |
|---|------|----------|---------------------|
| 1 | API keys were committed in `backend/.env` / `frontend/.env` | **High** | Files untracked + gitignored. **ACTION REQUIRED: rotate the exposed keys** (OpenAI/Anthropic/Gemini/etc.) at the provider — assume compromised. |
| 2 | Backend API has no authentication or rate limiting (`MOCK_AUTH`) | High | Not exposed publicly should be enforced operationally. Add auth + rate limiting before any public deployment (roadmap). |
| 3 | `databossx.db` and logs were committed (may contain processed content) | Medium | Untracked + gitignored. Review history if the DB held sensitive data; consider history scrub if needed. |
| 4 | LLM responses stored in SQLite without redaction | Medium | Documented; add redaction/retention policy (roadmap). |
| 5 | Paid API usage in `doto_image_commander` (OKCounty, OpenAI) | Medium | App has cost estimation + approval gating; operators must review Queue before bulk downloads. |
| 6 | Heavy/native OCR deps (paddlepaddle/paddleocr) hard to install | Medium | Guarded by platform marker; troubleshooting documented. Consider making them optional extras. |
| 7 | Overlapping/duplicated requirements files with divergent pins | Low/Med | Documented in `MAJOR_UPGRADE_BACKLOG.md`; consolidate later. |
| 8 | `deno.yml` CI runs against non-existent Deno code | Low | No-op; documented as removal candidate in `CI_SECURITY.md`. |
| 9 | `automation/parsing.py` LLM extraction is stubbed (regex only) | Low | Functional but limited; flagged for completion (roadmap). |
| 10 | GitHub Actions not all SHA-pinned / `setup-python@v3` outdated | Low | Documented in `CI_SECURITY.md`. |

## Top action for the owner
**Rotate every API key that was present in the committed `.env` files.** Removing
them from tracking does not undo prior exposure.
