# Recovery

Do not edit source evidence to repair a run. Preserve the failed run and its logs.

For an interrupted stage, use CLI `pipeline --resume` against the same project. The pipeline skips a stage only when its database status and all recorded artifact hashes remain valid; otherwise it archives retry artifacts and rebuilds that stage and downstream stages.

If the PID file is stale, `START` removes it only after confirming no matching process exists. `STOP` removes a stale PID file when the process no longer exists, but refuses a mismatched live process.

To restore generated state, stop the app, preserve the current `.runtime` and output directory, inspect a backup ZIP, and restore only the intended generated database/config/artifact paths. Never restore over the source corpus. SQLite WAL/SHM files require a cleanly stopped process. After recovery, run health checks and verify hashes/stage status before continuing.
