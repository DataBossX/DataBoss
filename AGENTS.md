# AGENTS.md — instructions for coding agents

DataBossX is a multi-app repo (FastAPI backend, React frontends, Playwright
automation, Streamlit OCR app). Read `docs/AI_REPO_MAP.md` first.

## Golden rules
1. **Never** read, print, or commit real secrets. Secrets live in gitignored
   `.env` files; only edit `*.env.example` (names + placeholders).
2. **Never** push to remote or open PRs unless explicitly asked.
3. Preserve behavior unless fixing a clearly identified bug/security issue —
   and add a test when you do.
4. Pause for destructive/irreversible actions, live migrations, paid API usage,
   or production credentials.

## Workflow
- Start: `git status`, confirm branch, run `python scripts/doctor.py`.
- Finish: `python scripts/test_all.py` and `python scripts/security_scan.py`
  must be clean. Update `docs/CHANGELOG_AI.md`.

## Commands
- Tests: `pytest` · Lint gate: `flake8 . --select=E9,F63,F7,F82`
- Backend: `cd backend && uvicorn server:app --reload --port 8001`
- Frontend: `cd frontend && yarn start`

Detailed rules live in `.cursor/rules/`.
