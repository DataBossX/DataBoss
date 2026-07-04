# PROJECT STATUS — Grocery Report

_Last updated: 2026-07-04 • Owner: automation/land-title production • Target: Monday, July 6 2026_

## 1. What this repo actually contains
`DataBossX/DataBoss` is a **code repository**, not a document store. A recursive scan
found **zero source title documents** (no PDFs, deeds, runsheets, ownership sheets, etc.)
in the cloud checkout. The real Grocery Report source documents live on the operator's
machine (assumed `D:\DataBoss\DataBossX_Final_Modular`), which the cloud cannot see.

Existing relevant code found:
- `automation/roger_mills_title_report_builder.py` — an excellent but **project-specific**
  local Excel-report builder (hardcoded to the "Roger Mills" job; Excel-only output).
- `automation/parsing.py`, `writer.py`, `status_logic.py` — Weld County scraper helpers
  (LLM stubs, rule-based status logic). Not a document-ingestion pipeline.
- `doto_image_commander/` — a Streamlit OCR/PDF app (Oklahoma county image puller).

**Conclusion:** there was no general, rerunnable ingestion→reconciliation→report pipeline
matching the Grocery Report mission. One has now been built.

## 2. What was built this session
A single-file, deterministic, **rerunnable** pipeline: **`grocery_report_pipeline.py`**
implementing all mission stages A–I, plus:
- `make_sample_data.py` — generates a clearly-labeled **synthetic** test corpus.
- `tests/test_grocery_pipeline.py` — 10 end-to-end tests (all passing).
- `requirements-grocery.txt` — pinned/optional dependency list.
- Planning docs: this file, `TODO_NOW.md`, `REPORT_PIPELINE_PLAN.md`, `QA_CHECKLIST.md`,
  `RUNBOOK.md`.

The pipeline is **stdlib-first**: it runs with no third-party packages, degrading
gracefully (CSV instead of XLSX, Markdown instead of DOCX, and a logged note where a PDF
has no text layer and no OCR backend is installed). It **never fabricates** title data:
unfound fields are left blank and flagged `REVIEW REQUIRED`.

## 3. Current pipeline state (verified against synthetic corpus)
| Stage | Output | Status |
| --- | --- | --- |
| A Inventory | `output/file_inventory.csv/.xlsx` | ✅ working |
| B Duplicates | `output/duplicate_candidates.csv`, `quarantine_plan.csv` | ✅ working (plan-only; non-destructive) |
| C Text extraction | `output/extracted_text/`, `source_text_index.csv` | ✅ txt/csv/xlsx/docx; PDF/OCR optional |
| D Classification | `output/document_classification.csv` | ✅ working (deterministic keyword rules) |
| E Structured extraction | `output/extracted_facts.csv/.xlsx` | ✅ working (regex; confidence + flags) |
| F Reconciliation | `output/reconciliation_table.xlsx`, `chain_summary.xlsx`, `conflicts_and_gaps.xlsx` | ✅ working |
| G Validation | `output/validation_report.xlsx`, `review_required.csv` | ✅ working (13 rules) |
| H Report assembly | `Grocery_Report_DRAFT.md/.docx`, `Executive_Summary.md`, `Curative_List.xlsx`, `Source_Index.xlsx` | ✅ working |
| I Dashboard | `output/status_dashboard.html/.xlsx` | ✅ working (RAG + % + Monday risk) |

## 4. The one hard blocker
**The real source documents are not in this environment.** No automated pipeline can
produce a real Grocery Report without them, and inventing facts is forbidden. Rodney must
run the pipeline locally against the real folder (one command — see `RUNBOOK.md`).

## 5. Monday delivery assessment
See `TODO_NOW.md` §Risk. **YELLOW** — the machinery is complete and verified; final
delivery depends on (a) running it on the real documents locally and (b) a title
professional reviewing the flagged `REVIEW REQUIRED` items. No red machinery blockers.
