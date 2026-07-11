# DataBossX Security

## 🚨 URGENT — Rotate these credentials NOW

Real API keys were committed to this repository in `backend/.env`. The file has
been removed from tracking, **but the keys remain in git history** and this
repository's history has been pushed to GitHub. Treat every one of these keys
as **compromised** and rotate (revoke + reissue) them immediately:

| Provider | Where to rotate |
| --- | --- |
| OpenAI (`OPENAI_API_KEY`, `sk-proj-…`) | https://platform.openai.com/api-keys |
| Anthropic (`ANTHROPIC_API_KEY` / `CLAUDE_API_KEY`, `sk-ant-…`) | https://console.anthropic.com/settings/keys |
| Google Gemini (`GEMINI_API_KEY`, `AIza…`) | https://aistudio.google.com/apikey |
| Google Drive (`GOOGLE_DRIVE_API_KEY`, `AIza…`) | https://console.cloud.google.com/apis/credentials |
| Qwen / DashScope (`QWEN_API_KEY`) | https://dashscope.console.aliyun.com/ |
| xAI Grok (`GROK_API_KEY`, `xai-…`) | https://console.x.ai/ |

Rotation checklist (do in this order):

1. Revoke each old key at the provider console (links above).
2. Issue a new key and put it **only** in a local, untracked `backend/.env`
   (copy `backend/.env.example`) or a proper secrets manager.
3. Check each provider's usage dashboard for unfamiliar spend since the commit.
4. Enable GitHub **secret scanning + push protection** on this repository:
   Settings → Code security and analysis → enable "Secret scanning" and
   "Push protection".
5. (Optional but recommended) Rewrite history to purge the secrets
   (`git filter-repo --path backend/.env --invert-paths`) — note that rotation,
   not history rewriting, is what actually removes the risk.

## Rules going forward

- **No secrets in git.** `.gitignore` blocks `.env` files everywhere; only
  `.env.example` placeholder files may be committed.
- **CI secret scanning.** The `secret-scan` job (gitleaks) runs on every push
  and pull request and fails the build if a credential pattern is detected.
- **Separate dev and prod credentials.** Never reuse a production key in a
  development environment or paste one into a prompt.
- **Client data is not code.** Source title documents, workbooks, and client
  deliverables belong in the document store / local drives, not this repo.
  Generated `output/` artifacts are already gitignored.

## Reporting

If you find a committed secret or a security defect, rotate first, then open a
private issue or contact the repository owner directly. Do not open a public
issue containing the secret itself.
