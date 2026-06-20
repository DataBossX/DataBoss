# DataBossX

**Local-first safety tooling for the title / runsheet workflow.**

DataBossX automates the tedious, error-prone parts of title research — inspecting
Excel runsheets, following document hyperlinks, running OCR, and drafting
suggested corrections — while guaranteeing it **never silently mutates your source
data**. Every action follows one operating law:

> **inspect → backup → edit → test → log → register. No silent edits.**

Source workbooks are fingerprinted before and after every run and the pipeline
aborts if the hash changes. AI suggestions are written to a *copy*, never the
original. Secrets are reported by location and type only — never by value.

---

## Quickstart

```bash
# 1. Install (editable, with dev tooling)
python -m pip install -e ".[dev]"

# 2. Run the full safety-first pass (health → backup → scan → map → inspect →
#    review copy → source-hash proof → diagnostics)
databossx first-task

# 3. Or drive individual tools
databossx health
databossx scan --fail-on-tracked          # CI gate: fails if a secret is in git
databossx inspect path/to/runsheet.xlsx
databossx preflight --max-rows 3          # gated TitlePreviewFixer preflight

# 4. Interactive menu
databossx menu          # (equivalent to: python -m databossx.ui.command_center)
```

Without installing, everything is runnable via `python -m databossx <command>`.

## CLI commands

| Command | What it does |
|---------|--------------|
| `health` | Runtime / dependency / directory health report; flags tracked `.env` files |
| `backup` | Zip backup + SHA-256 manifest (excludes `.env`, logs, db, keys) |
| `scan [--fail-on-tracked]` | Detect secrets; report location + type only. CI gate option |
| `map` | Markdown project tree (skips excluded dirs) |
| `mock-workbook [-o PATH]` | Generate a fake runsheet — no real client data |
| `inspect WORKBOOK` | Read-only inspect + export hyperlinks to CSV |
| `review WORKBOOK` | Create a review copy with AI columns on the **copy only** |
| `fingerprint WORKBOOK` | SHA-256 + size of a workbook (proves source unchanged) |
| `preflight [--source --max-rows --budget]` | Gated TitlePreviewFixer 3-row preflight (mock OCR) |
| `diagnostics` | Build a support bundle (excludes secrets) |
| `first-task` | Run the entire safety pass end to end |
| `menu` | Launch the interactive command center |

Add `--json` to any command for machine-readable output. Run
`databossx <command> --help` for full options.

## Architecture

```
databossx/
├── core/      paths · health · secret_scan · backup · project_map
│              file_guard · diagnostics        (safety primitives)
├── excel/     workbook_fingerprint · mock_workbook
│              workbook_inspector · review_workbook
├── title/     document_schema · ocr_validator · confidence_gate
│              row_compare · mock_ocr · titlepreviewfixer
├── agents/    cost_guard                       (budget gate before paid OCR)
├── ui/        command_center                   (interactive menu)
├── cli.py     scriptable subcommand interface
└── __main__.py  `python -m databossx`
```

All artifacts (reports, backups, diagnostics, review copies) are written to
predictable, git-ignored directories defined in `databossx/core/paths.py`, which
is the single source of truth for what must **never** be committed.

See [`databossx/README.md`](databossx/README.md) for per-module safety
guarantees and the required review-column contract.

## Safety guarantees

- **Source is immutable.** Workbooks are SHA-256 fingerprinted before/after; a
  changed hash aborts the run.
- **AI writes to copies only.** Review columns are added to a duplicate workbook.
- **Secrets never leave.** Backups, maps, and diagnostics exclude `.env`, `.auth`,
  `*.pem`, `*.db`, logs, and key files. The scanner reports locations, not values.
- **Cost is gated.** A budget guard runs before any (would-be) paid OCR call.

## Development

```bash
python -m pip install -e ".[dev]"
pytest                       # unit suite (tests/)
flake8 .                     # lint
mypy                         # type-check databossx/
black databossx tests        # format
```

The `backend_test.py` integration tests require a running backend and are
**opt-in**: run them with `RUN_BACKEND_INTEGRATION=1 pytest backend_test.py`.

CI (`.github/workflows/python-app.yml`) installs dependencies, runs the flake8
syntax/undefined-name gate, and runs the unit suite on every push and PR to
`main`.

## Security

If you discover an exposed credential, **rotate it immediately** — untracking a
file does not remove it from git history. Run `databossx scan --fail-on-tracked`
to detect secrets that are tracked by git. See [`CONTRIBUTING.md`](CONTRIBUTING.md)
for the secrets policy.
