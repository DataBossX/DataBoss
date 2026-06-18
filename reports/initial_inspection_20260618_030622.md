# DataBossX — Initial Inspection Report

**Timestamp:** 20260618_030622
**Operator:** Claude Code agent (branch `claude/databossx-setup-zaumek`)

> Operating law followed: **Inspect first. Backup second. Edit third. Test fourth. Log everything. No silent edits.**

## 1. Current working directory
`/home/user/DataBoss` — a **Linux remote execution container** (ephemeral cloud sandbox), **not** the Windows `D:\DataBoss\DataBossX_Final_Modular` / `D:\Desktop\DataBossX` the prompt assumes. Windows launchers (`.bat`) and `.venv` flows cannot be executed here; they can be authored but only run on the user's Windows machine.

## 2. Files / folders detected
Existing app (full-stack, "emergent" template):
- `backend/` — FastAPI `server.py` (+ tracked `.env`, stray `=x.y.z` pip-artifact files)
- `frontend/` — React app (+ tracked `.env`)
- `automation/` — `playwright_bot.py`, `parsing.py`, `status_logic.py`, `writer.py`
- `doto_image_commander/` — Oklahoma county land-records app
- `mineral_deal_room/` — Vite/React "Target Factory"
- `config/settings.toml`, `prompts/`, `scripts/`, `tests/` (was empty), `logs/`
- Root junk: `databossx.db` (tracked), `databossx.log` (tracked)

New this session (`databossx/` package): `core/`, `excel/`, `ui/` safety tooling.

## 3. App entry points
- `backend/server.py` (FastAPI)
- `doto_image_commander/app.py`
- `mineral_deal_room` (Vite dev server)
- **New:** `python -m databossx.ui.command_center` (safety command center)

## 4. Python version
`Python 3.11.15`.

## 5. Requirements / dependency files
`requirements.txt`, `backend/requirements.txt`, `doto_image_commander/requirements.txt`, `frontend/package.json`, `mineral_deal_room/package.json`. `openpyxl==3.1.5` and `pandas` are declared; installed and verified for the Excel tooling.

## 6. Existing tests
`tests/` contained only an empty `__init__.py`; root `backend_test.py` exists. **Added** `tests/test_databossx_safety.py` (11 tests, all passing).

## 7. Existing logs / reports / backups
`logs/databossx.log` (tracked — now untracked). No `reports/` or `backups/` existed; created this session.

## 8. Potential secrets / protected folders (no values printed)
🚨 **`backend/.env` was tracked in git with live-looking API keys** (OpenAI, Anthropic/Claude, Gemini, Grok, Qwen, Google Drive). `frontend/.env` also tracked. See `secret_scan_*.md`. **Remediated** (untracked + gitignored) — but they remain in git history, so **the keys must be rotated.** No `Horizon`/`Penterra` folders are present in this container.

## 9. Highest-risk files
1. `backend/.env` — exposed credentials (highest).
2. `databossx.db`, `logs/databossx.log` — tracked private data.
3. `backend/=*.*.*` — accidental pip-redirect files (removed).
4. `automation/playwright_bot.py` — live browser automation (review before running).

## 10. Next safest action
Done this session: backup → secret scan → project map → mock workbook → inspect → review copy → **source-hash-unchanged proof** → self-test → diagnostics. **Next:** user rotates exposed keys; then the gated TitlePreviewFixer 3-row preflight (Gates 1–11) against a real (mock-first) workbook.
