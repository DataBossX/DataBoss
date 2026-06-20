# Contributing to DataBossX

Thanks for helping improve DataBossX. This project guards real client title data,
so contributions are held to a safety-first bar.

## The operating law

Every feature must honor:

> **inspect → backup → edit → test → log → register. No silent edits.**

Concretely:

- Never mutate a source workbook. Write to a copy and fingerprint the source
  before/after.
- Never print, log, or commit secret *values*. Report location + type only.
- Anything that could cost money (paid OCR/LLM calls) must pass `agents/cost_guard`
  first.

## Development setup

```bash
python -m pip install -e ".[dev]"
```

## Before you open a PR

```bash
pytest                                  # unit suite must pass
flake8 . --select=E9,F63,F7,F82         # the hard CI gate (syntax / undefined names)
flake8 .                                # full lint (warnings)
mypy                                    # type-check databossx/
black --check databossx tests           # formatting
databossx scan --fail-on-tracked        # no secrets may be tracked by git
```

CI runs the flake8 gate and the unit suite on every push and PR to `main`. Keep
both green.

## Secrets policy

- `.env`, `*.auth`, `*.pem`, `*.db`, `token.json`, and `credentials.json` are
  **never** committed. They are excluded by `.gitignore` and by
  `databossx/core/paths.py`.
- Commit `.env.example` templates with placeholder values only.
- If a secret is ever committed, **rotate the credential immediately** — removing
  the file in a later commit does not remove it from git history. A history
  rewrite (`git filter-repo`) plus a force-push is required to scrub it, and that
  is a deliberate, reviewed operation.

## Tests

- Unit tests live in `tests/` and run by default.
- `backend_test.py` holds live integration tests that need a running backend.
  They are opt-in: `RUN_BACKEND_INTEGRATION=1 pytest backend_test.py`.
- New safety guarantees should ship with a test that fails if the guarantee is
  broken (e.g. "source hash unchanged after review copy").

## Style

- Target Python 3.10+, use type hints, prefer small pure functions returning
  dataclasses.
- Match the existing module layout: a `run(...)` entry point that writes a
  timestamped artifact under the directories in `core/paths.py`.
