# DataBoss Multi-AI Fire Watchers

A local-first control plane for supervising Cursor, ChatGPT, Claude, Gemini, Codex, Grok, and future agents through one standardized queue and evidence model.

> **Status: PHASE 0 FOUNDATION.** This package currently validates and atomically
> places a single job package into a local agent inbox. It is not yet a live
> watcher or a bidirectional agent bus. See
> [`DIRECTIVE_GAP_REPORT.md`](DIRECTIVE_GAP_REPORT.md).

## Safety model

- No arbitrary shell execution.
- Approval tokens are validated in memory and excluded from stored jobs.
- Original evidence is read-only.
- Handled submissions publish at most one claim, rejection, or failure receipt per job ID.
- Approval-required jobs fail closed when no token is provided.
- Copied claim inputs are hashed.
- This foundation does not promote or release client deliverables.

## Standard lifecycle

`inbox -> claimed -> running -> completed | failed | rejected | quarantine`

The target lifecycle will use these artifacts:

- `CLAIM.json`
- `HEARTBEAT.json`
- `PROGRESS.json`
- `RESULT.json`
- `ERROR.json`
- `HASHES.json`
- `METRICS.json`
- `COMPLETE.json`

## Quick start

```powershell
cd databoss_orchestrator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m databoss_orchestrator.cli init --root D:\DataBoss\control_plane
python -m databoss_orchestrator.cli health --root D:\DataBoss\control_plane
```

The initial implementation supports validated file-drop claims only. A copied
job is `claimed`, never `completed`; terminal result collection remains open.
