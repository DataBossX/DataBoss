# Drive command-center watcher

This watcher processes JSON jobs in a Google Drive for Desktop synchronized
command center. It is deliberately limited to a built-in no-op operation. It
does not execute shell text, dynamic Python, scripts, or arbitrary paths.

The repository is public. Never commit a real Drive folder ID, synchronized
path, job, receipt, client artifact, or runtime log here. Keep the populated
configuration and all control artifacts in the private command center.

## Windows activation

Run these commands in a terminal opened at the private DataBossX checkout:

```powershell
python -m automation.drive_command_center.windows_setup detect --folder-id "<folder-id>"
```

Detection succeeds only when exactly one folder has all expected directories
and a matching `canonical_folder_id` in `watcher_config.json` or
`WATCHER_ONLINE.json`. If no control artifact exists yet, set
`DATABOSSX_COMMAND_CENTER` to the known synchronized path, add the matching
configuration there, and run detection again. Ambiguous or absent paths fail
closed.

Before changing existing watcher files, copy them into a timestamped isolated
backup directory. Copy the templates from this directory into the command
center as:

- `watcher_config.example.json` → `watcher_config.json`
- `job.schema.json` → `schemas/job.schema.json`
- `approved_scripts.example.json` → `approved_scripts.json`

Populate only the private copy of `watcher_config.json`. Confirm its `root` is
the exact detected path, its poll interval remains 60 seconds, and
`local_state_dir` points to a watcher-only directory under `%LOCALAPPDATA%`
outside every synchronized folder. Successful jobs create local proof markers
there; startup is denied if the self-test's marker and synchronized receipts do
not match.

Run one poll:

```powershell
python -m automation.drive_command_center.watcher `
  --config "<command-center>\watcher_config.json" --once
```

Do not enable startup unless the required no-op receipt is successful. The
installer enforces that gate:

```powershell
python -m automation.drive_command_center.windows_setup install-startup `
  --config "<command-center>\watcher_config.json" `
  --self-test-job-id "<self-test-job-id>"
```

The least-privileged startup method is a command file in the current user's
Startup folder. It does not use the registry or administrator privileges.
Disable it by moving `DataBossXDriveWatcher.cmd` out of that Startup folder.

## State and controls

The watcher atomically moves a valid input from `inbox` to `claimed` before
creating its acknowledgment. It then moves the input to `running`, writes a
heartbeat, and finally archives the input plus terminal receipt in `completed`.
Malformed or suspicious inputs are quarantined; schema or operation violations
are rejected. Runtime failures produce a terminal receipt in `failed`.

Additional controls include a single-instance lock, SHA-256 input hashes,
duplicate ID/content detection, stale-job quarantine, atomic JSON writes,
structured JSONL logs, bounded retries, path and operation allowlists, file-size
and filename limits, and graceful signal handling.
