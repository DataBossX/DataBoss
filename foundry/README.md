# DataBossX Foundry

The thin, verifiable bootstrap layer every DataBossX module runs on. The core
is a **general automation platform** — domain logic (Wyoming Abstracts,
Oklahoma Title, OCR, CRM) installs later as plugins under `/plugins` and core
code never imports plugins.

```powershell
# from the repo root
cd foundry
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\databossx doctor
```

| Command | What it does |
| --- | --- |
| `databossx doctor` | Detects Python, pip, uv, Node, npm, Git, Docker, Tesseract, Poppler, LibreOffice, Ghostscript, Java; writes `doctor_report.json`; exits nonzero until clean. `--install` runs the platform install commands. |
| `databossx env <project>` | Creates an isolated venv with a versioned lockfile; repairs broken venvs idempotently (broken venvs are quarantined, never deleted). |
| `databossx new <project>` | Scaffolds `PROJECT.json`, `STATUS.json`, `TODO.md`, `PLAN.md` + `inbox/ work/ outputs/ proofs/`. Never overwrites existing files. |
| `databossx discover` | Scans `D:/Desktop/Horizon` and `D:/Desktop/Penterra`, skips completed projects, writes ranked `registry.json` with missing-artifact flags. |
| `databossx run <project>.<task>` | Runs a task declared in `PLAN.md` with structured JSONL logs, timing, versioned output, and rollback on failure. |
| `databossx plugins list\|validate\|run` | Manages `/plugins`. Validation never executes plugin code (AST-only). |

Read [ARCHITECTURE.md](ARCHITECTURE.md) for the design and
[OPERATIONS.md](OPERATIONS.md) for the runbook. Tests: `pytest tests`
(coverage gate: 80%+ on `src/databossx`).
