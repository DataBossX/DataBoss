# DataBossX Foundation Architecture

This document describes the baseline application layer scaffolded on top of the
project structure. Everything here is **stdlib-only** so it runs and tests
anywhere without installing dependencies.

## Layers

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Config | `app/config.py` | Load non-secret settings from `config/settings.toml`; read secrets **only** from the process environment on demand; never log or return raw secret values (`redact`, `secret_status`). |
| Logging | `app/logging_setup.py` | Single shared audit trail to `logs/databossx.log` + console. |
| Guardrails | `tools/guardrails.py` | The Golden Law in code: `safe_write` (never overwrites, writes `_REVIEW_<ts>`), `is_protected_path` (blocks Horizon/Penterra), `timestamped_backup`, `wrap_untrusted` / `scan_for_injection`. |
| Tools | `tools/registry.py` | Declarative `name -> callable` registry for agents/workflows. |
| Agents | `agents/base.py` | `BaseAgent`: every action appends a JSONL proof record to `agent_outputs/<name>.jsonl`. Example: `agents/example_echo_agent.py`. |
| Workflows | `workflows/runner.py` | Sequential runner with per-step audit logging; halts on first failure and returns a complete `RunResult`. |
| Data | `scripts/init_db.py` / `app/db.py` | Idempotent SQLite schema (`documents`, `extractions`, `audit_log`) at `DB_PATH`, plus thin insert/audit helpers. |
| LLM | `tools/llm.py` | `LLMClient` uses litellm when the lib + provider key are present; otherwise `is_live` is False and agents use their offline path. Never logs secrets. |
| Ingest | `tools/ingest.py` | `load_rows` for the DSU/OFFSET notice lists — CSV via stdlib, XLSX via openpyxl when installed. |
| Extractor | `agents/extractor.py` | Untrusted text -> strict JSON (contract in `prompts/extractor_user.md`); deterministic regex fallback offline. |
| Reasoner | `agents/reasoner.py` | Chronological docs -> ownership decision (contract in `prompts/reasoner_user.md`); offline path faithfully implements the prompt's rules. |
| Pipeline | `workflows/extraction_pipeline.py` | `run_pipeline`: extract every doc -> reason -> persist documents/extractions/audit_log as proof. Runs fully offline. |

## Security invariants (enforced, not just documented)

- **No overwrites** — `safe_write` is the only sanctioned write path; it refuses
  to clobber existing files and refuses protected roots entirely.
- **No secrets** — config never parses `.env`; it only checks env-var presence.
- **Untrusted by default** — county documents / OCR text pass through
  `wrap_untrusted`, which delimits them as data and counts injection flags.
- **Every action leaves proof** — agents write JSONL; workflows log every step;
  the DB has an `audit_log` table.

| Recorder | `tools/weld_client.py` | Weld County client — **network OFF by default** (opt in via `allow_network`/`DATABOSSX_ALLOW_NETWORK=1`); throttled, polite UA; captures raw docs to `quarantine/` as wrapped untrusted data. |
| Driver | `workflows/notice_list_driver.py` | Turns notice-list rows into pipeline runs via a pluggable `resolver` (inline corpus, local files, or the live recorder client). |
| Report | `app/report.py` | Renders a title-review markdown report; written via `safe_write` (never overwrites). |
| CLI | `app/cli.py` | `health` / `initdb` / `ingest` / `run-section` — argparse entrypoint. |

## Running things

```bash
python scripts/init_db.py                       # create/verify the master DB
python -m unittest discover -s tests -p "test_*.py"   # run the test suite (30 tests)
python scripts/health_check.py                  # baseline health check
python -m agents.example_echo_agent             # see the agent contract in action

# CLI
python -m app.cli ingest data/notice_list.csv
python -m app.cli run-section --owner "Rodney Gille" --section "Sec 1" \
    --docs docs.json --out reports
```

`run-section` reads `docs.json` = `[{"source": "...", "text": "..."}, ...]` and
writes `reports/<Section>_REVIEW_<ts>.md`.

## Dependency note

The container this was built in has only the Python 3.11 standard library
available (`tomllib`, `sqlite3`, `logging`, `unittest`). Heavier libraries listed
in `requirements.txt` (pandas, openpyxl, litellm, playwright, OCR) are for the
full pipeline and are not required by this foundation layer or its tests.
