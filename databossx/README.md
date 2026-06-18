# DataBossX safety tooling

Local-first safety baseline for the DataBossX title/runsheet workflow.
Built under the operating law: **inspect → backup → edit → test → log → register. No silent edits.**

## Run

```bash
# One safety-first pass (health, backup, secret scan, map, mock workbook,
# inspect, review copy, source-hash proof, diagnostics):
python -m databossx.ui.command_center --first-task

# Interactive menu:
python -m databossx.ui.command_center

# Tests:
python -m pytest tests/test_databossx_safety.py -q
```

## Modules

| Module | Purpose | Safety guarantee |
|--------|---------|------------------|
| `core/paths` | Artifact paths + exclusion rules | Single source of truth for what is never committed |
| `core/health` | Runtime/dep/dir health | Flags tracked `.env` files |
| `core/secret_scan` | Detect secrets by pattern | Reports location/type only — **never values** |
| `core/backup` | Zip backup + SHA-256 manifest | Excludes `.env`, logs, db, backups, keys |
| `core/project_map` | Markdown tree map | Skips excluded dirs |
| `core/file_guard` | Guarded copy/delete | No overwrite, no protected-area writes, dry-run |
| `core/diagnostics` | Support bundle | Excludes `.env`/`.auth`/keys |
| `excel/workbook_fingerprint` | SHA-256 of `.xlsx` | Proves source unchanged |
| `excel/mock_workbook` | Fake runsheet | No real client data |
| `excel/workbook_inspector` | Read-only inspect + link CSV | Never saves the source |
| `excel/review_workbook` | Review copy + AI columns | Edits the **copy only** |

## Required review columns (added to copy only)

`AI_Status, AI_Confidence, Suggested_Document_Date, Suggested_Recorded_Date,
Suggested_Type, Suggested_Book, Suggested_Page, Suggested_Grantor,
Suggested_Grantee, Suggested_Legal, Suggested_Notes, Review_Reason`

## Roadmap (not yet built)

Browser login/OCR (`title/`, `browser/`), agent router/tournament (`agents/`),
registry SQLite DBs, Windows `.bat` launchers (author-only on Linux), and the
gated TitlePreviewFixer 3-row preflight. These are stubs/menu placeholders and
are **not** claimed as complete.
