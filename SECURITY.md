# DataBossX Security

## Immediate incident: rotate exposed credentials

`backend/.env` was committed to Git history. Removing it from the current tree
does not revoke or erase those values. Treat every credential previously stored
there as compromised and rotate it now:

| Credential | Rotation page |
| --- | --- |
| OpenAI | https://platform.openai.com/api-keys |
| Anthropic / Claude | https://console.anthropic.com/settings/keys |
| Gemini | https://aistudio.google.com/app/apikey |
| Google Cloud / Drive | https://console.cloud.google.com/apis/credentials |
| xAI / Grok | https://console.x.ai/ |
| Qwen / DashScope | https://dashscope.console.aliyun.com/ |
| MongoDB | Rotate the database user password and connection string |

Do not paste replacement values into issues, chats, logs, source files, or
screenshots. Store them in a local ignored `.env` file or a secrets manager.

History rewriting is optional defense in depth and requires a coordinated
force-push. It does **not** replace key rotation. Do not rewrite shared history
without notifying every collaborator and preserving a recovery mirror.

## Required controls

- Commit only `.env.example` templates with blank or unmistakably fake values.
- Treat every `REACT_APP_*` value as public because it is shipped to browsers.
- Give connectors read-only, folder/repository-scoped credentials by default.
- Never place secrets in model prompts, model memory, audit events, or artifacts.
- Require an exact, expiring human approval for any external write.
- Bind workers to the minimum files, tools, and network destinations needed.
- Redact secret values in diagnostics; report only type and location.
- Preserve immutable audit records for credential use and policy decisions.

## Local checks

Install the hooks once:

```bash
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

CI scans the current repository tree with Gitleaks. Historical exposure is
tracked separately because scanning all history would intentionally continue to
find the already-known incident until a coordinated history rewrite occurs.

## Reporting

Report security problems privately to the repository owner. Never open a public
issue containing a key, token, client document, title evidence, or private path.
