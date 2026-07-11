# DataBossX

The canonical repository for DataBossX — an AI-assisted land-title production
system (Oklahoma cursory title reports, Wyoming abstracts, document intake,
ownership math, QA).

## Layout

| Path | What it is |
| --- | --- |
| `core/land_title_os/` | Control layer every agent must use: project manifests, master asset inventory, evidence ledger (authority-ranked), hash-chained run receipts, staged file promotion with human gates, open-item register, exact-fraction QA engine |
| `projects/` | One machine-readable manifest per land-section project (e.g. `OK-BECKHAM-32-11N-25W`) |
| `horizon/` | Title-report engine: exact-fraction interest math, OGL↔runsheet chaining, validation gates, zero-destruction versioning (`README` inside) |
| `grocery_report_pipeline.py` | Rerunnable document ingestion→classification→extraction→reconciliation→report pipeline (stages A–I) |
| `automation/` | Verified project-specific builders (Roger Mills) + scraper helpers |
| `doto_image_commander/` | Streamlit OCR / Oklahoma county image app (component source) |
| `mineral_deal_room/`, `backend/`, `frontend/` | Component source, not yet under the promotion system |
| `MASTER_PLAN.md` | The Top-100 moves mapped to actual status, governance rules, execution order |
| `SECURITY.md` | Secret handling + **urgent key-rotation checklist** |

## Ground rules

1. **No secrets in git.** Only `.env.example` placeholders. CI runs gitleaks on every push.
2. **No client documents in git.** Documents live in Drive/local stores; manifests reference them by ID.
3. **No fabrication.** Engines flag `REVIEW REQUIRED` / `Needs Examiner Review` instead of guessing.
4. **No silent finals.** Deliverables advance only through `core/land_title_os/promotion.py` (SOURCE → … → APPROVED → DELIVERED); the last two stages require a named human.
5. **No receipt, no work.** Agent runs record hash-chained receipts (`core/land_title_os/receipts.py`).

## Tests

```bash
pip install -r requirements.txt pytest
pytest
```
