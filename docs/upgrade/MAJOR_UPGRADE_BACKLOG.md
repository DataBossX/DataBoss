# Major Upgrade Backlog

Upgrades that are risky, require migration work, or need owner sign-off. Not
applied automatically. Apply one at a time, run `scripts/test_all.py`, commit.

## Dependency consolidation
- **Three Python requirements files** (`requirements.txt`,
  `backend/requirements.txt`, `doto_image_commander/requirements.txt`) with
  overlapping and **divergent** pins, e.g. `fastapi` appears as `0.110.1`,
  `0.114.2`, and `>=0.110.1`; `tenacity` as `8.2.3` and `9.0.0`. The root file
  also has duplicate lines (last one wins). **Action:** pick one source of truth
  per app, deduplicate, align versions, verify imports.

## Framework majors (verify changelogs + test before adopting)
- **React 19** (`frontend`) on `react-scripts` 5 (CRA, effectively in
  maintenance). Consider migrating off CRA to Vite for the frontend, matching
  `mineral_deal_room`. Non-trivial; schedule deliberately.
- **react-router-dom 7** (`frontend`) vs **6** (`mineral_deal_room`) — align.
- **pydantic 2.x** is already in use; ensure all models are v2-style.

## CI / tooling
- `actions/setup-python@v3 → v5`; pin third-party actions by SHA.
- Add `pip-audit` / `npm audit` gating once dependency files are consolidated.

## OCR stack
- `paddlepaddle` / `paddleocr` are heavy native deps (Linux-only markers). Decide
  whether to keep, make optional extras, or replace with a lighter OCR.

## Process
For each item: read release notes, branch, apply, `python scripts/test_all.py`,
record outcome here, then commit. Pin anything that cannot be upgraded with the
reason.
