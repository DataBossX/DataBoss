# DataBoss Multi-AI Fire Watchers

A local-first control plane for supervising Cursor, ChatGPT, Claude, Gemini, Codex, Grok, and future agents through one standardized queue and evidence model.

## Safety model

- No arbitrary shell execution.
- No secret values in jobs, logs, or receipts.
- Original evidence is read-only.
- Every state transition produces a timestamped receipt.
- High-impact actions require an approval token issued by Rodney.
- Outputs are hashed before promotion.
- Client deliverables remain HOLD_NO_RELEASE until release gates pass.

## Standard lifecycle

`inbox -> claimed -> running -> completed | failed | rejected | quarantine`

Every agent job uses the same artifacts:

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
python -m databoss_orchestrator.cli watch --root D:\DataBoss\control_plane
```

The initial implementation supports safe file-drop adapters. Browser/API-specific adapters can be added behind the same interface without changing the queue contract.
