# BASELINE RECEIPT — pre-tournament state

- Receipt ID: `DBX-BASELINE-2026-08-01`
- Produced: 2026-08-01
- Produced by: Claude Code (`claude-opus-5`), tournament director
- Purpose: freeze the pre-tournament truth so any later failure can be
  attributed to the tournament or exonerated as pre-existing.

---

## 1. Repository state

```
branch      claude/databossx-tournament-director-ot7k5d
HEAD        582d95161cf8220fb37f5224e21e57dcc5c3121c
origin/main 582d95161cf8220fb37f5224e21e57dcc5c3121c
diff        git diff --stat origin/main...HEAD  ->  (empty)
worktree    clean (git status: "nothing to commit, working tree clean")
worktrees   1  (/home/user/DataBoss only)
tracked     227 files
remote heads 117
open PRs    40 (all draft)
```

Files changed by this receipt: **none**. No application code was modified to
produce it.

## 2. Toolchain actually present

| Tool | Present | Note |
| --- | --- | --- |
| Python | 3.11.15 | `/usr/local/bin/python` |
| Node | v22.22.2 | |
| npm | 10.9.7 | |
| `requests` | yes | only third-party Python package importable |
| `pytest` | **NO** | |
| `pydantic` | **NO** | hard import in `horizon/models.py` |
| `openpyxl` | **NO** | lazy import in `horizon/pipeline.py`, `report_io.py` |
| `lxml` | **NO** | lazy import in `horizon/repair.py` |
| `pandas`, `fastapi`, `sqlalchemy` | NO | |

### Dependency installation is blocked, not merely absent

```
$ python -m pip install pytest
ERROR: Could not find a version that satisfies the requirement pytest (from versions: none)

$ curl -o /dev/null -w '%{http_code}' https://pypi.org/simple/pytest/
403

$ curl -o /dev/null -w '%{http_code}' https://registry.npmjs.org/react
403
```

`pypi.org`, `files.pythonhosted.org`, and `registry.npmjs.org` sit in the agent
proxy's `noProxy` list and return **403 — destination not allowed by this
session's egress policy**. Per `/root/.ccr/README.md` this is an organisation
policy denial: it must be reported, not retried or routed around. It was not
retried or routed around.

**Therefore the canonical command `python -m pytest -q` from `README.md` cannot
be executed in this environment.** Any claim that it passed would be false.

## 3. Baseline test result — obtained via a declared substitute harness

To get a real signal rather than no signal, the director wrote a stdlib-only
substitute harness **outside the repository** (in the session scratchpad, not
committed, not on any competitor path):

- `harness/pytest.py` — a shim providing only `raises`, `fixture`, `mark`
  (including `parametrize` expansion), `skip`, `fail`, `approx`.
- `harness/run_baseline.py` — collects `test_*` functions from `tests/`,
  resolves module-level fixtures plus `tmp_path` / `tmp_path_factory`, expands
  `parametrize`, and classifies each outcome.

**This is not pytest.** Fixture scoping, plugin behaviour, collection order,
`conftest` hooks, and assertion rewriting all differ. Results below are
*harness-derived* and are labelled as such everywhere they are used. They are a
smoke signal, not a certification.

### Result

```
PASS     61
FAIL      1
ERROR     0
BLOCKED  11   (whole modules: import failed on a missing third-party dependency)
SKIP      0
```

| Test file | Harness result |
| --- | --- |
| `test_databossx_foundation.py` | 3 pass |
| `test_grocery_pipeline.py` | 9 pass, **1 fail** |
| `test_horizon_chaining.py` | 7 pass |
| `test_horizon_foundation.py` | 6 pass |
| `test_horizon_interest.py` | 29 pass (parametrize-expanded) |
| `test_horizon_versioning.py` | 7 pass |
| `test_horizon_artifacts.py` | BLOCKED — `No module named 'pydantic'` |
| `test_horizon_audit_fixes.py` | BLOCKED — `No module named 'pydantic'` |
| `test_horizon_pipeline.py` | BLOCKED — `No module named 'pydantic'` |
| `test_horizon_repair_orchestrator.py` | BLOCKED — `No module named 'pydantic'` |
| `test_horizon_review_fixes.py` | BLOCKED — `No module named 'pydantic'` |
| `test_horizon_review_fixes2.py` | BLOCKED — `No module named 'pydantic'` |
| `test_horizon_validation.py` | BLOCKED — `No module named 'pydantic'` |
| `test_horizon_controlled_loop.py` | BLOCKED — `No module named 'openpyxl'` |
| `test_horizon_review_fixes3.py` | BLOCKED — `No module named 'openpyxl'` |
| `test_horizon_review_fixes5.py` | BLOCKED — `No module named 'openpyxl'` |
| `test_horizon_review_fixes6.py` | BLOCKED — `No module named 'openpyxl'` |

11 of 17 test modules — including **every workbook-integrity, repair,
validation, and controlled-loop test**, i.e. exactly the safety-critical
surface — cannot execute here at all.

## 4. KNOWN PRE-EXISTING FAILURES (not caused by the tournament)

### KF-1 — `test_grocery_pipeline.py::test_all_outputs_exist`

```
AssertionError: Missing outputs: ['file_inventory.xlsx', 'extracted_facts.xlsx',
'reconciliation_table.xlsx', 'chain_summary.xlsx', 'conflicts_and_gaps.xlsx',
'validation_report.xlsx', ...]
```

Cause: environmental, not a code defect. `grocery_report_pipeline.py` degrades
to CSV when `openpyxl` is absent (it logs
`WARN openpyxl missing -> wrote CSV fallback for ...`), which is the documented
and intended behaviour in `README.md` / `RUNBOOK.md`. The test asserts the
`.xlsx` filenames unconditionally, so the graceful-degradation path fails its
own test suite. This is a **test-vs-design mismatch that predates the
tournament**. It is recorded here so it is never attributed to a competitor.

### KF-2 — 11 blocked modules

Cause: environmental (no PyPI egress). Pre-existing. Not attributable to any
competitor.

### KF-3 — Client identifier present in the public repository

`horizon/CONTROLLED_LOOP.md` contains, in the public repo:

- project id `DBX-OK-BECKHAM-32-11N-25W`
- private local paths of the form `D:/DataBossX/beckham32/final_delivery/...`
- work-order path `projects/OK-BECKHAM-32-11N-25W/work_orders/WO-SECTION32-QA-001.json`

`docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md` classifies real project
manifests and private paths as **Internal**, and `.gitignore` already blocks
`projects/OK-*/`. Open draft **PR #59 — "security: sanitize public workbook QA
example"** appears to address exactly this and is unmerged.

This is a **pre-existing publication-policy exposure**, recorded, not fixed by
the director (Phase 0 forbids code changes and this is Ryan's call, not the
tournament's). It is escalated in the response to Ryan.

### KF-4 — Holds are not machine-enforced

See `TOURNAMENT_MANIFEST.md` §3. No hold registry, no hold check, no test.
Pre-existing.

## 5. Writer-lease check

- Local worktrees: 1 (`/home/user/DataBoss`). No competing checkout.
- Working tree clean; no stash; no rebase/merge in progress.
- Director branch is byte-identical to `origin/main` (empty three-dot diff).
- No lock file, lease file, or writer-claim file exists in the repository.
- 40 open draft PRs and 117 remote heads exist, but the most recent remote
  update is `2026-07-26`; nothing has pushed in the last 5 days.
- **Caveat, stated honestly:** "no active writer" is inferred from repository
  state only. This environment cannot observe the private Windows machine, so it
  cannot prove no human or agent is writing there. Treated as **unverified for
  the private side**; see blocker B-3 in the response to Ryan.

## 6. Reproduction

```bash
git -C /home/user/DataBoss rev-parse HEAD          # 582d951...
git -C /home/user/DataBoss status --porcelain      # empty
python <scratchpad>/harness/run_baseline.py /home/user/DataBoss
```

The harness lives in the session scratchpad
(`.../scratchpad/harness/`), deliberately outside the repository and outside
every competitor workspace, so it cannot be mistaken for project code or be
imported by a competitor.
