# Foundry Operations Runbook

Everything below is reproducible on a fresh clone. Windows 11 / PowerShell is
the primary target; the same commands work on Linux/macOS by swapping path
separators (`.venv/bin/...` for `.venv\Scripts\...`).

## 1. Install (fresh clone)

```powershell
cd D:\Desktop\DataBossX\foundry     # or wherever the repo is cloned
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

Every command below is `.venv\Scripts\databossx ...` (or activate the venv
once with `.venv\Scripts\Activate.ps1` and just call `databossx`).
`python -m databossx ...` works identically.

## 2. Check the machine

```powershell
databossx doctor              # checks all 12 tools, writes doctor_report.json
databossx doctor --install    # additionally runs the winget/apt install commands
databossx doctor --core-only  # only require python/pip/git (bootstrap minimum)
```

* Exit `0` = clean. Exit `2` = missing required tools; the output lists the
  exact install command per tool (winget on Windows). Re-run until clean.
* `doctor_report.json` is written to the current directory (`--out PATH` to
  choose). It records every tool, found path, and version.

## 3. Create and run a project

```powershell
databossx new demo            # scaffolds projects/demo (never overwrites)
databossx run demo.hello      # runs the generated hello task
```

After `run`:

* structured log: `projects/demo/work/logs/hello_run_v001.jsonl`
* versioned output: `projects/demo/outputs/hello_result_v001.json`
* status: `projects/demo/STATUS.json` (`last_run` + history)

Add your own tasks to `projects/demo/PLAN.md` under `## Tasks` (see
ARCHITECTURE.md for the bullet format). If a task fails, its partial output
files are moved to `projects/demo/work/rollback/<run>/` — check there, fix,
re-run. Nothing is deleted.

## 4. Give a project an isolated environment

```powershell
databossx env demo
```

Creates `projects/demo/.venv` (uv when installed, else `python -m venv`),
installs `projects/demo/requirements.txt` when present, writes
`work/locks/requirements_vNNN.lock` + `requirements.lock`. Re-running is
idempotent; a corrupted venv is quarantined to `work/trash/` and rebuilt.
Tasks automatically prefer the project venv via the `{python}` placeholder.

## 5. Inventory the backlog

```powershell
databossx discover
```

Scans `D:/Desktop/Horizon` and `D:/Desktop/Penterra` (override:
`--root PATH` repeatable, or `DATABOSSX_DISCOVER_ROOTS`), skips completed
projects, ranks the rest by missing artifacts (`no_ocr`, `no_report`,
`no_qa`) and recency, and writes `registry.json` at the root plus a
versioned snapshot in `foundry_state/`.

## 6. Plugins

```powershell
databossx plugins list
databossx plugins validate                 # all plugins; exit 1 if any invalid
databossx plugins run safety_kernel:smoke
databossx plugins run qa_auditor:smoke
databossx plugins run safety_kernel:versioned_write --json '{"folder":"D:/tmp/out","stem":"report","ext":".txt","data":"hello"}'
```

Installing a plugin = dropping a directory with a valid `plugin.json` under
`/plugins`. `validate` proves the manifest and entrypoints without running
any plugin code; `run` is the only path that executes it. Install a plugin's
Python deps (from `requires.python`) into whatever environment runs it.

## 7. Tests and the coverage gate

```powershell
cd foundry
.venv\Scripts\python -m pytest tests
.venv\Scripts\python -m coverage run -m pytest tests
.venv\Scripts\python -m coverage report   # gate: 80%+ on src/databossx
```

## 8. Environment variables

| Variable | Effect |
| --- | --- |
| `DATABOSSX_ROOT` | Overrides the root (projects/, plugins/, registry.json location). |
| `DATABOSSX_DISCOVER_ROOTS` | Overrides discovery roots (`;`-separated on Windows, `:` on Linux). |

## 9. Secrets

Human-provisioned only, via a local `.env` or an encrypted store. The Foundry
never generates, fetches, uploads, or logs secrets — and no Foundry command
asks for one. Never commit `.env`.

## 10. Changing the Foundry itself

Changes to passing code are proposal-only: write
`proposals/<date>_<slug>/PROPOSAL.md` + `changes.diff` (see
`proposals/README.md`). A human reviews, applies, and re-runs the test suite.
