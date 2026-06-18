# BUGBOT — PR review guidance for DataBossX

Focus reviews on substance, not style. Prioritize, in order:

1. **Secrets & data exposure** — any `.env`, key, token, credential, `*.db`, or
   hardcoded API key being committed; secrets in logs or LLM-response storage.
2. **Security bugs** — missing input validation/sanitization, path traversal,
   SQL/command injection, SSRF, missing HTTP timeouts, wildcard CORS with
   credentials, bare `except:`, unbounded uploads/loops.
3. **Correctness / breaking changes** — behavior changes to public API
   endpoints, DB schema, or shared helpers; broken imports; stdlib modules added
   to requirements (e.g. `sqlite3`).
4. **Tests** — bug fixes without regression tests; new security helpers without
   unit tests; tests that hard-fail when optional heavy deps are absent (should
   use `pytest.importorskip`).
5. **CI/CD risk** — workflows missing least-privilege `permissions:`, untrusted
   PR text interpolated into shell, unpinned third-party actions, broad artifact
   uploads.
6. **Operator usability** — does it still run via the documented commands /
   `.bat` launchers? Are docs (`README`, `RUNBOOK`) still accurate?

Ignore pure formatting/style nitpicks unless they harm maintainability or
correctness. Be concise; cite `file:line`.
