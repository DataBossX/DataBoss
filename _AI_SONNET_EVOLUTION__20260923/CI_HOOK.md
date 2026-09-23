# CI hook: OBSERVE + PROPOSE only, on every pull request

This describes how to wire `evolution_loop.py` into GitHub Actions so it
runs automatically on every PR **without ever writing to the repository**.
It is intentionally the least powerful mode the module supports.

## What this job does and does not do

Does:

- Checks out the PR head commit, read-only.
- Runs `evolution_loop.py --mode observe-propose`, which performs OBSERVE
  and PROPOSE only, walks the checkout for file **names** (never contents),
  and stops. `run_cycle(..., mode="observe-propose")` returns before
  AUTHORIZE/BUILD/TEST/ADVERSARIAL/RECEIPT/LEARN ever run — there is no
  sandbox, no receipt ledger, no learning memory file, in this mode.
- Writes the resulting JSON to a workflow artifact (uploaded by the runner,
  not committed to the repository).
- Runs `test_evolution_loop.py` so a change to the module itself is checked
  by its own test suite before it can be trusted.

Does not:

- Commit, push, or open any PR or comment.
- Request any permission beyond `contents: read`. No `pull-requests: write`,
  no `issues: write`, no `id-token: write`. (See "On PR comments" below if a
  team decides to opt into that separately — it is not part of this hook.)
- Call any external API, model, or secret. `evolution_loop.py` is
  stdlib-only; the workflow needs nothing but a Python interpreter.
- Run `--mode full`. The full mode (BUILD/TEST/ADVERSARIAL/RECEIPT/LEARN)
  is for local or a separate, explicitly-scoped job — never wired to "every
  PR" in this hook, to keep the default CI footprint at L0/L1 only.

## Workflow file

Create `.github/workflows/evolution-loop-observe.yml`:

```yaml
name: Evolution loop (observe + propose only)

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read

concurrency:
  group: evolution-loop-observe-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  observe-propose:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Checkout PR head (read-only)
        uses: actions/checkout@v4
        with:
          persist-credentials: false

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Run the module's own tests
        working-directory: _AI_SONNET_EVOLUTION__20260923
        run: python3 -m unittest test_evolution_loop -v

      - name: Run OBSERVE + PROPOSE (no repo writes)
        working-directory: _AI_SONNET_EVOLUTION__20260923
        run: |
          python3 evolution_loop.py \
            --repo-root "${GITHUB_WORKSPACE}" \
            --mode observe-propose \
            --out "${RUNNER_TEMP}/evolution-proposals.json"

      - name: Upload proposals as a workflow artifact
        uses: actions/upload-artifact@v4
        with:
          name: evolution-loop-proposals-${{ github.event.pull_request.number }}
          path: ${{ runner.temp }}/evolution-proposals.json
          retention-days: 14
```

Notes on each control:

- `permissions: contents: read` at the workflow level is the maximum this
  job ever needs, and it caps the default `GITHUB_TOKEN` even if a later
  step were added carelessly. This directly satisfies "never expand
  permissions."
- `--out "${RUNNER_TEMP}/..."` writes to the *runner's* temp directory, not
  into the checked-out working tree — the checkout itself never gets a new
  file. Combined with `persist-credentials: false`, there is nothing in
  this job that could push even if a bug tried to.
- `concurrency` + `cancel-in-progress` keeps at most one observe job per PR
  running at a time, mirroring the module's own `SingleCycleLock` intent at
  the CI layer (full mode's lock only matters within a single process; this
  is the CI-level equivalent for repeated pushes to the same PR).
- `timeout-minutes: 5` bounds the job; `observe-propose` mode has no
  subprocess calls and no I/O beyond directory listing, so this should
  finish in seconds — a long run is itself a signal something is wrong.

## Reading the result

The artifact is a `CycleResult` JSON (see `evolution_loop.py:CycleResult`).
For `observe-propose` mode, the fields that matter are:

```json
{
  "terminal_state": "PROMOTED_DRAFT_PR_ELIGIBLE" | "NO_ELIGIBLE_PROPOSAL",
  "receipt": {
    "stage_hashes": {"observe": "<hash>", "propose": "<hash>"},
    "notes": ["observe-propose mode: no filesystem writes performed"]
  }
}
```

`PROMOTED_DRAFT_PR_ELIGIBLE` here only means "at least one proposal was
generated" — it is **not** a claim that BUILD/TEST/ADVERSARIAL passed,
because those stages did not run. A human reviewing the artifact decides
whether the proposal is worth a follow-up `--mode full` run in a separate,
explicitly-triggered job (see below), never automatically from this hook.

## Optional, explicitly opt-in: posting a PR comment

Posting the proposal as a PR comment requires `pull-requests: write` on the
`GITHUB_TOKEN`, which is a permission this default hook deliberately does
not request. If a team decides that trade-off is worth it:

- Put it in a **second, separate** workflow file so the observe-only job
  above keeps its minimal permission set.
- Scope `permissions: pull-requests: write` on that second job only, not on
  the observe job.
- Still never let it call `--mode full`; it should only ever render the
  artifact from the observe-only job into a comment.

This repository's default posture, per the instructions this cycle was
designed under, is to *not* add that second workflow unless a maintainer
explicitly asks for it.

## Running `--mode full` in CI (not part of this hook, documented for completeness)

If a team later wants a scheduled (not per-PR) job that also exercises
BUILD/TEST/ADVERSARIAL/RECEIPT/LEARN against the *synthetic fixture* built
into `test_evolution_loop.py` (not the real repository), that belongs in a
separate `schedule:`-triggered workflow, writing its `--runtime-dir` to
`${{ runner.temp }}`, uploading `receipts.jsonl` and
`learning_quarantine.jsonl` as artifacts, and passing neither
`--reviewed-by` nor `--review-note` (so nothing is auto-marked "reviewed" —
see `LEARNING_MEMORY.md`). That job still must not run on `pull_request`
events, must not have write permissions, and must not attempt to open or
merge anything.
