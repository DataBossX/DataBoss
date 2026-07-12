# DataBossX Secure Orchestration

## Trust boundary

The `core` package is the local trusted kernel. Google Drive or a synced Drive
folder is a message transport, never a command shell. Jobs select only a
compiled operation from `config/approved_operations.yaml`; job content cannot
provide Python, shell, imports, subprocess arguments, output roots, credentials,
or permissions.

The command center uses:

- atomic `inbox → claimed → running → completed|failed` moves;
- `rejected` for malformed or expired jobs and `quarantine` for duplicates;
- SQLite WAL state with legal-transition checks;
- one exclusive watcher lock;
- ACK, heartbeat, and terminal receipts;
- a database trigger that prohibits audit update and delete;
- hash-linked, redacted audit events;
- bounded job size, age, runtime fields, paths, and operation names.

Only the orchestrator changes job state. Approved operations that need a
project-specific work order fail closed until that work order is implemented
and hash-bound.

## Providers and routing

`core.providers` records provider capability and credential *presence*. It never
returns credential values. OpenAI, Anthropic, Google, xAI, Ollama, LM Studio,
and deterministic mock profiles are supported. Model names are selected by
configuration/discovery, not treated as permanent constants. Hard privacy and
capability filters run before routing. A provider call is not evidence.

No external provider was invoked for the source-limited Section 32 run because
there was no source evidence and no approved paid task. Deterministic title
math continues to use `horizon.interest` and `fractions.Fraction`.

## Evidence and release

Claims require citations at the result-contract boundary. Exact acreage,
ownership, royalty, lease status, WI, NRI, burdens, HBP, depth, and corporate
continuity remain unresolved unless operative evidence supports them.
Technical verification never grants release. A failed critical gate, absent
human landman review, or absent approver authorization always yields
`HOLD_NO_RELEASE`.

The source-limited Section 32 executor creates empty, schema-bearing ledgers,
blockers, a release-gate matrix, a completion receipt, and a SHA-256 ledger. It
does not create a release-candidate XLSX without the controlling template,
because doing so would falsely imply template conformance.

## Operator commands

```text
python -m core.cli health
python -m core.cli process-once
python -m core.cli run-section32
```

On Windows, use the root launchers:

- `START_DATABOSSX.bat`
- `STOP_DATABOSSX.bat`
- `HEALTH_CHECK.bat`
- `RUN_SECTION32.bat`
- `OPEN_COMMAND_CENTER.bat`
- `VIEW_LATEST_RESULTS.bat`

Runtime data belongs under `runtime/` and is intentionally excluded from Git.
Real client evidence stays in approved private systems.
