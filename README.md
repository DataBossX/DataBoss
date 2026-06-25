# DataBoss

Mineral & land-records data automation platform for Oklahoma (Anadarko Basin
acquisition workflows). The repo bundles several cooperating components:

| Path | Component |
|------|-----------|
| `backend/` | FastAPI service (`server.py`) — document/OCR/LLM analysis API, SQLite-backed |
| `frontend/` | React UI (yarn) |
| `mineral_deal_room/` | "Mineral Deal Intelligence Room" — Vite/React target-scoring app |
| `doto_image_commander/` | Oklahoma county land-records image automation (Streamlit + OKCountyRecords API) |
| `automation/` | Playwright bot + LLM extractor/reasoner for recorded instruments |
| `scripts/` | Operational tooling, incl. the Cursory Title Report generator |
| `reports/` | Generated reports (HTML/Excel) |
| `prompts/`, `config/` | LLM prompts and run configuration |

## Setup

```bash
python -m pip install -r requirements.txt
cp backend/.env.example backend/.env   # then fill in real values (never commit .env)
```

## Running

```bash
uvicorn backend.server:app --reload        # backend API
python scripts/cursory_title_report.py     # generate a cursory title report
```

## Security notes

- Secrets live only in `.env` files, which are git-ignored. Required keys are
  documented in `backend/.env.example`.
- `CORS_ALLOW_ORIGINS` controls allowed browser origins (comma-separated).
