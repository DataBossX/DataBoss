# Security & Secrets Handling

## TL;DR for contributors

- **Never commit a `.env` file.** Only `*.env.example` templates belong in git.
- Copy each template to a real `.env` and fill in your own keys:
  ```bash
  cp .env.example .env                 # root (Supabase / app config)
  cp backend/.env.example backend/.env # backend DB + LLM provider keys
  cp frontend/.env.example frontend/.env
  ```
- A pre-commit hook (gitleaks) and a CI job block secrets from being pushed.
  Install the hook once: `pip install pre-commit && pre-commit install`.

## Secret hygiene rules

1. Real credentials live only in untracked `.env` files or your platform's
   secrets manager — not in source, not in `.example` files, not in chat tools
   or third-party editor extensions that offer to "auto-detect" your keys.
2. `REACT_APP_*` values are compiled into the browser bundle and are **public**.
   Never put a private API key behind a `REACT_APP_` variable.
3. Rotate any key the moment it lands somewhere it shouldn't (a commit, a log,
   a screenshot, a pasted snippet). Untracking a file does **not** remove it
   from existing git history.

## ⚠️ Known historical exposure — rotate these keys

`backend/.env` and `frontend/.env` were previously committed to this repository.
They have now been removed from tracking and added to `.gitignore`, but the
values still exist in past git history. **Treat every key that was in
`backend/.env` as compromised and rotate it at the provider:**

| Variable                | Where to rotate                                        |
| ----------------------- | ------------------------------------------------------ |
| `ANTHROPIC_API_KEY`     | https://console.anthropic.com/settings/keys            |
| `CLAUDE_API_KEY`        | same Anthropic console (revoke/reissue)                |
| `OPENAI_API_KEY`        | https://platform.openai.com/api-keys                   |
| `GEMINI_API_KEY`        | https://aistudio.google.com/app/apikey                 |
| `GROK_API_KEY`          | https://console.x.ai                                   |
| `QWEN_API_KEY`          | Alibaba DashScope console                               |
| `GOOGLE_DRIVE_API_KEY`  | https://console.cloud.google.com/apis/credentials      |
| `MONGO_URL` credentials | rotate the DB user's password / connection string      |

Rotating invalidates the leaked values so they're useless even though they
remain in history.

### Optional: purge the secrets from git history

Untracking stops future exposure but the old values are still reachable via
`git log`. To scrub them from history entirely you must rewrite history and
force-push (coordinate with all collaborators first):

```bash
# Using git-filter-repo (recommended)
pip install git-filter-repo
git filter-repo --path backend/.env --path frontend/.env --invert-paths
git push --force --all
```

Even after a history rewrite, **rotate the keys** — assume anyone who cloned
the repo already has the old values.

## Reporting a vulnerability

Found a security issue? Email the maintainer rather than opening a public
issue, and avoid posting credentials, tokens, or stack traces containing
secrets.
