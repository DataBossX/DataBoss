# DataBossX Runbook — how to run this

Plain-English operating instructions. Cross-platform commands are shown; on
Windows you can double-click the matching `.bat` file in the repo root.

## 0. First-time setup

1. Install **Python 3.10+** and **Node.js 20+ / Yarn**.
2. Open a terminal in the project folder.
3. Run the doctor to confirm your machine is ready:
   ```bash
   python scripts/doctor.py        # Windows: RUN_DOCTOR.bat
   ```
4. Create your secret files from the templates (these are gitignored):
   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```
   Open each `.env` and paste in your real API keys. **Never commit them.**

## 1. Backend API (document OCR + LLM analysis)

```bash
pip install -r requirements.txt
cd backend
uvicorn server:app --reload --port 8001      # Windows: RUN_APP.bat
```
- Health check: open http://localhost:8001/api/health
- The API needs `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` to do
  LLM analysis; without them it still runs (those services show "unavailable").

## 2. Frontend (control center UI)

```bash
cd frontend
yarn install
yarn start                                    # opens http://localhost:3000
```
Set `REACT_APP_BACKEND_URL` in `frontend/.env` to the backend URL.

## 3. Mineral Deal Room dashboard

```bash
cd mineral_deal_room
yarn install
yarn dev                                       # http://localhost:5173
```

## 4. DOTO Image Commander (OK county records)

```bash
cd doto_image_commander
./run.sh                                        # creates venv, starts Streamlit:8501
```
Configure `OKCOUNTY_API_KEY` and `OPENAI_API_KEY` in `doto_image_commander/.env`.
**Note:** this app makes _paid_ API calls; approve items in the Queue page before
downloading to control spend.

## 5. Automation bot (Weld County scraper)

```bash
run.bat            # Windows: installs deps, installs Playwright, runs the bot
# or:
python -m playwright install chromium
python -m automation.playwright_bot
```
The browser opens visibly so you can solve any CAPTCHA. Needs the Excel workbook
referenced in `config/settings.toml` present in the working directory.

## Routine maintenance

| When | Do |
|------|----|
| Before a work session | `python scripts/doctor.py` |
| Before committing | `python scripts/test_all.py` |
| Weekly | `python scripts/security_scan.py` and `python scripts/update_deps_safe.py` |
| Before risky changes | `python scripts/backup_project.py` |

## Stopping services

Press `Ctrl+C` in the terminal running each app. The Docker `entrypoint.sh`
handles SIGTERM/SIGINT to stop backend + nginx together.
