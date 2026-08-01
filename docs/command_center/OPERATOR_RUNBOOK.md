# OPERATOR RUNBOOK — DataBossX Command Center

Release state: **FOR REVIEW — HOLD — NO EXTERNAL RELEASE**
Nothing here deploys anything, exposes a port beyond loopback, or touches client
data.

## Prerequisites

Python 3.11+. No package installation is required — the stack is standard
library only (ADR-0001).

## Start the control plane

```bash
cd /path/to/DataBoss
PYTHONPATH=services/control_api python -m command_center.http_api
```

Serves `http://127.0.0.1:8787`. **Loopback only** — a non-loopback host raises
`NotAuthorized` by design. Each start creates a fresh temporary database, so
restarting gives a clean synthetic environment.

Open the URL in a mobile-sized viewport, or install it as a PWA from a browser
that offers "Add to Home Screen".

## Run the vertical slice headlessly

```bash
PYTHONPATH=services/control_api python -m command_center.slice
```

Prints the full trace and a summary containing the command, task, job, and
receipt IDs, the receipt hash, the Drive read-back result, the idempotency
proof, the hold-removal refusal, and the watcher verdicts.

## Run the tests

```bash
# Command Center suite - 154 tests, all execute
PYTHONPATH=services/control_api python -m unittest discover -s tests/command_center -t . -p "test_*.py"

# One suite at a time
PYTHONPATH=services/control_api python -m unittest tests.command_center.test_red_team -v

# Legacy suite under the stdlib-compat runner (NOT pytest - see below)
python tests/command_center/legacy_runner.py --verbose
```

**Read the legacy runner's output carefully.** It is a faithful subset, not
pytest. Cases it cannot execute are reported `SKIPPED-UNSUPPORTED`, never as
passing. When a networked runner is available, run real `pytest` and use that
instead.

## Run visual QA

```bash
# with the server running
python scripts/command_center_visual_qa.py
```

Drives headless Chromium over CDP across 7 viewport cases, writes PNGs and
`visual_qa_report.json` to `evidence/command_center/screenshots/`, and exits
non-zero on any finding.

## Daily operating loop

1. Open the PWA. Read the hold banner first — it is always present.
2. Read the six questions. If "What is blocked?" is non-zero, triage first.
3. Read the Best Next Move card, including *why now* and *if it fails*.
4. Expand "Withheld moves" to see what policy is refusing and on what grounds.
5. Act on one move at a time. One writer, one scope, one lease.
6. After execution, read the receipt: what changed, what proves it, next step.

## Common situations

**"Resource scope is already leased."** Another writer holds it. Wait for
release or expiry. Force release only if the holder is genuinely dead:

```python
kernel.release_lease(owner_actor, lease_id, force=True)   # OWNER only, loudly audited
```

**"Approval already consumed."** Correct behaviour — approvals are single-use.
Issue a new one; a retry should be a fresh human decision.

**"Fencing sequence is stale."** The lease changed hands. Do not retry with the
old envelope. Claim a fresh lease and build a new one.

**A job failed.** Read `failure_reason` on the receipt. The rollback already
ran; nothing was partially applied.

**The audit chain reports invalid.** Treat as an incident, not a cleanup task.
Follow §7 of `ROLLBACK_AND_RECOVERY.md`. Do not repair the ledger.

**A move you want is withheld.** Read its `vetoes`. If a hold is the reason, the
answer is a separate authorized human lane — not this system, not a retry, and
not a model.

## Emergency stop

```bash
touch /path/to/runner/workroot/../STOP     # matches RunnerConfig.kill_switch_path
```

The runner refuses all work with `KillSwitchEngaged` before any verification.
Delete the file to resume.

## Things an operator must never do

- Remove or weaken a hold. Every path refuses, and every attempt is audited.
- Bind the API to a public interface.
- Put real client evidence, credentials, or absolute paths into any command,
  parameter, receipt, or screenshot.
- Present a `SIMULATED` result as real.
- Force-balance an unbalanced ownership chain. The remainder is reported
  honestly; that is the correct output.
- Overwrite an accepted artifact. Create a new version instead.
- Push to another agent's branch.

## Where to look

| Question | File |
| --- | --- |
| What was verified at the start? | `BASELINE_RECEIPT.md` |
| What is missing? | `CURRENT_GAP_REPORT.md` |
| How is it built? | `CANONICAL_ARCHITECTURE.md`, `adr/` |
| What is attacked and defended? | `THREAT_MODEL.md` |
| What data may go where? | `DATA_CLASSIFICATION.md` |
| Which states are legal? | `STATE_MACHINES.md` |
| How are moves ranked? | `BEST_MOVES_SCORING.md` |
| What can the runner do? | `LOCAL_RUNNER_CONTRACT.md` |
| How does Drive work? | `DRIVE_CONTROL_ROOM_CONTRACT.md` |
| Is it canary-ready? | `PRIVATE_CANARY_GATES.md` |
| How do I recover? | `ROLLBACK_AND_RECOVERY.md` |
| What happened this cycle? | `IMPLEMENTATION_RECEIPT.md` |
