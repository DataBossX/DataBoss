# Foundry Architecture

Phase 0 of DataBossX Genesis v2. The Foundry is the bootstrap layer: it knows
how to check a machine, isolate environments, scaffold and run projects,
inventory the work backlog, and load plugins. It contains **zero domain
logic**.

## Laws (operating rules in force)

1. **Plugin architecture.** Core is a general automation platform. Domain
   logic ships as plugins under `/plugins` with a `plugin.json` manifest.
   Core code never imports plugins; plugin code executes only on an explicit
   `databossx plugins run` (or a smoke test that calls the same loader).
2. **Nothing ships without a passing test.** Every module here has typed
   code, tests, logging, and error handling. CI gate: pytest green with 80%+
   coverage on `src/databossx` (currently ~94%).
3. **Zero destruction.** No Foundry command deletes or overwrites user data:
   outputs are versioned `*_vNNN.ext` files, broken venvs are quarantined to
   `work/trash/`, failed-run outputs are moved to `work/rollback/`, scaffold
   never touches existing files, and `registry.json` keeps versioned
   snapshots under `foundry_state/`. A destructive operation would require an
   explicit `--confirm` flag; Phase 0 deliberately has none.
4. **Secrets are human-provisioned** (.env / encrypted store). The Foundry
   never generates, fetches, uploads, or logs secrets — no module here reads
   or writes credential material at all.
5. **Self-improvement is proposal-only.** Changes to passing code are written
   to `/proposals` as markdown + diff and reviewed by a human. Never
   auto-merged.
6. **Windows 11 first.** Default root `D:/Desktop/DataBossX`; every command
   runs in PowerShell. The code is cross-platform (CI runs on Linux) but all
   defaults and install hints put Windows first.

## Layout

```
<root>                        # D:/Desktop/DataBossX (or the git checkout)
├── foundry/                  # this package
│   ├── src/databossx/        # core (stdlib-only, no third-party deps)
│   │   ├── cli.py            # argparse CLI: doctor|env|new|discover|run|plugins
│   │   ├── config.py         # root + discovery-root resolution (env overrides)
│   │   ├── doctor.py         # tool detection, install commands, report JSON
│   │   ├── envs.py           # venv create/repair + versioned lockfiles
│   │   ├── scaffold.py       # project skeleton (never overwrites)
│   │   ├── planfile.py       # PLAN.md '## Tasks' parser (strict, line-numbered errors)
│   │   ├── runner.py         # task execution: JSONL logs, timing, rollback
│   │   ├── discover.py       # Horizon/Penterra backlog scan -> ranked registry.json
│   │   ├── versioned.py      # _vNNN write discipline for core outputs
│   │   ├── logs.py           # stderr logging + append-only JSONL event logs
│   │   ├── errors.py         # FoundryError hierarchy with exit codes
│   │   └── plugins/          # manifest spec + AST-only validating loader
│   └── tests/                # pytest suite (isolated tmp roots, fake runners)
├── plugins/                  # installed plugins (each: plugin.json + modules)
│   ├── safety_kernel/        # wraps horizon.versioning + horizon.audit
│   └── qa_auditor/           # wraps horizon.validation (+ horizon.models)
├── proposals/                # proposal-only self-improvement (md + diff)
├── projects/                 # created by `databossx new`
├── foundry_state/            # registry snapshots, quarantine trash
└── registry.json             # latest ranked backlog (stable pointer)
```

## Root and path resolution (`config.py`)

`DATABOSSX_ROOT` env var → else `D:/Desktop/DataBossX` when it exists → else
the enclosing checkout (walk up to `.git` or `foundry/pyproject.toml`) → else
cwd. Discovery roots: `DATABOSSX_DISCOVER_ROOTS` (path-separator-separated) →
else `D:/Desktop/Horizon` + `D:/Desktop/Penterra` plus `<root>/Horizon` +
`<root>/Penterra`, keeping the ones that exist. Everything downstream takes a
`FoundryConfig`, so tests run against throwaway roots.

## Doctor

`ToolSpec` declares, per tool: candidate executables, version args, and exact
install commands for windows (winget), linux (apt), darwin (brew). Detection
is `shutil.which` + a version probe that reads stdout *and* stderr (java).
pip falls back to `python -m pip`. All lookups are injectable, so the whole
matrix is unit-tested without touching the host. `doctor_report.json` records
every tool, version, path, and hint. Exit codes: `0` clean, `2` unclean.
`--core-only` restricts the required set to python/pip/git (bootstrap
essentials) for machines that only run the Foundry itself; the default
requires all twelve tools. `--install` executes the platform's install
command for each missing tool, then re-checks.

## Env

`.venv` per project, created with `uv` when available (fallback:
`python -m venv`). Health check = venv python exists and runs. A broken venv
is **moved** to `work/trash/venv_broken_vNNN` and rebuilt — idempotent and
non-destructive. `requirements.txt` is installed when present. Every run
freezes a versioned lockfile `work/locks/requirements_vNNN.lock` and mirrors
the latest to `requirements.lock` (a stable pointer for tooling).

## Scaffold + Plan + Runner

`databossx new demo` produces a plan that is immediately runnable
(`databossx run demo.hello`). PLAN.md declares tasks under `## Tasks`:

```markdown
### hello
- desc: smoke task
- cmd: {python} -c "print('hello from demo')"
- timeout: 60
```

`{python}` resolves to the project venv python when present (else the Foundry
interpreter); `{project_dir}/{inbox}/{work}/{outputs}/{proofs}` expand to
project paths. Multiple `- cmd:` bullets are sequential steps; the first
nonzero exit stops the task.

The runner writes an append-only JSONL event stream per run
(`work/logs/<task>_run_vNNN.jsonl`: task_start / step_start / step_end /
rollback / task_end with per-step timing), a versioned result artifact
(`outputs/<task>_result_vNNN.json`) on success, and updates `STATUS.json`
(last_run + capped history). **Rollback:** the runner snapshots `outputs/`
before the task; on failure every newly created output file is moved to
`work/rollback/<run>/` so `outputs/` only ever holds artifacts of successful
runs — and nothing is deleted.

## Discover

Each first-level directory under a discovery root is a project. Completed
projects (STATUS.json status complete/done/delivered, or a COMPLETE/DONE
marker file) are skipped. Open projects are flagged: `no_ocr` (source
pdf/tiff/images without OCR output), `no_report` (no `*report*` workbook or
document), `no_qa` (no QA/audit artifact or populated proofs/qa folder).
Rank = 10 per missing artifact + recency bonus (≤30 days: +3, ≤90: +1);
ties break to most recent. Output: `registry.json` (stable) + versioned
snapshot in `foundry_state/`. Scans are capped at 5,000 files per project.

## Plugin system

`plugin.json` manifest (see `src/databossx/plugins/manifest.py` docstring for
the full spec): `name` (slug = directory name), `version` (semver),
`description`, `entrypoints` (`{"smoke": "entry:smoke"}` →
`module:function`), `permissions` (closed vocabulary: `filesystem:read`,
`filesystem:write`, `subprocess`, `network` — anything else fails
validation), `requires.tools` (doctor keys) and `requires.python` (pip
requirement strings).

The loader validates **without executing untrusted code**: JSON parse →
manifest field validation (collecting all errors) → AST-only entrypoint
check (module file parses; target function defined at top level). Import and
execution happen exclusively in `call_entrypoint`, reached only by an
explicit `databossx plugins run <plugin>:<entrypoint> --json '{...}'`.
Entrypoint contract: `def fn(payload: dict) -> JSON-able`.

## Absorbed plugins (Phase 0 deliverable 7)

The repo's existing safety kernel and QA auditor are **wrapped, not
rewritten**:

* **safety_kernel** wraps `horizon/versioning.py` (versioned `_vNNN` writes,
  never overwrite) and `horizon/audit.py` (append-only, timestamped audit
  trail). Entrypoints: `versioned_write`, `latest`, `audit`, `smoke`.
* **qa_auditor** wraps `horizon/validation.py` + `horizon/models.py` — the
  validation gate (interest reconciliation, schema checks, Golden Source
  instrument/column gates; never fabricates data). Entrypoints:
  `audit_report`, `smoke`.

Both add the repo root to `sys.path` and delegate to the originals. Smoke
tests live in `foundry/tests/test_absorb.py` and run through the real plugin
loader against the real `/plugins` directory.

## Exit codes

`0` success · `1` any `FoundryError` (bad input, failed task, invalid
plugin) · `2` doctor unclean.
