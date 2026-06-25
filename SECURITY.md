# Security

## Active incident: API keys committed to git history

`backend/.env` was committed with **7 live API keys** (OpenAI, Anthropic ×2,
Google ×2, xAI, Qwen). The file has been removed from the working tree and is
now git-ignored, **but the keys remain in git history** (commits `8147df6`,
`ff76a4b`, and the auto-commit) on `main`. Anyone who cloned or forked the repo
still has them.

### Remediation — in order

1. **Rotate / revoke every key NOW** (this is the real fix — history scrubbing
   does not un-leak an already-pushed key):

   | Env var | Provider console |
   |---------|------------------|
   | `OPENAI_API_KEY` | platform.openai.com → API keys → revoke + recreate |
   | `ANTHROPIC_API_KEY`, `CLAUDE_API_KEY` | console.anthropic.com → API keys |
   | `GEMINI_API_KEY`, `GOOGLE_DRIVE_API_KEY` | console.cloud.google.com → APIs & Services → Credentials |
   | `GROK_API_KEY` | console.x.ai → API keys |
   | `QWEN_API_KEY` | dashscope/Alibaba Cloud console |

   After rotating, put the new values in a **local, untracked** `backend/.env`
   (see `backend/.env.example` for the contract).

2. **Purge the files from history** (after rotation + notifying collaborators):

   ```bash
   git clone --mirror <repo-url> backup.git      # backup first
   CONFIRM=PURGE ./scripts/scrub_secrets_history.sh
   # then force-push all refs (script prints the exact commands)
   ```

3. **Verify**: the `Secret Scan` GitHub Actions workflow scans full history and
   will stay **red until both rotation context is cleared and history is
   scrubbed** — that red status is intentional until step 2 is done.

## Prevention (already wired up)

- **`.gitignore`** blocks `.env*`, `*.db`, `*credentials*.json`, `*token*.json`.
- **`backend/.env.example`** documents required vars without real values.
- **`.pre-commit-config.yaml`** runs `gitleaks` + `detect-private-key` on every
  commit. Enable locally once: `pip install pre-commit && pre-commit install`.
- **`.github/workflows/secret-scan.yml`** runs `gitleaks` over full history on
  every push/PR to `main`, failing the build on any detection.
- **`.gitleaks.toml`** extends the default ruleset with LLM-provider key
  patterns and allowlists example/placeholder files.

## Reporting

Found a vulnerability? Email the maintainer rather than opening a public issue.
