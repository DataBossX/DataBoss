# DataBossX Command Center

A working, local, dark-mode operations dashboard for Penterra and Horizon
work. Zero heavy dependencies -- pure Python standard library on the
backend, vanilla HTML/CSS/JS on the frontend -- so it starts instantly on
whatever Python is already installed.

## Run it (dev / any OS)

```bash
cd command_center
python3 server.py
```

Then open the printed `http://127.0.0.1:<port>` URL (it auto-picks a free
loopback port starting at 8765, and refuses to start a second instance
against the same runtime folder).

## Run it (Ryan, Windows)

Double-click `00_START_DATABOSSX.bat`. Use `00_STOP_DATABOSSX.bat`,
`00_DIAGNOSTICS_DATABOSSX.bat`, and `00_REPAIR_DATABOSSX.bat` as needed.

## Configuration

Project roots default to `C:\DataBoss\Penterra` and `C:\DataBoss\Horizon`.
Override with environment variables if your layout differs:

- `DATABOSSX_PENTERRA_ROOT`
- `DATABOSSX_HORIZON_ROOT`
- `DATABOSSX_DB_PATH` (defaults to `command_center/runtime/databossx.db`)
- `DATABOSSX_PORT` (defaults to `8765`)
- `DATABOSSX_LOCAL_MODEL_URL` (defaults to `http://127.0.0.1:11434`, Ollama's default)

## What's real right now

- **Discovery**: metadata-only scan (names, sizes, mtimes) of every
  subfolder under the two lane roots -- no hashing, no OCR, no AI calls.
- **Actions**: Update Me / Inspect Project / Find Missing Evidence /
  Build Worklist / Run QA / Open Best Candidate all execute for real
  against whatever is on disk. Every write lands only inside a project's
  own `_DataBossX_Working` subfolder -- source files are never touched.
- **Next Best Move**: a deterministic scoring pass (see `next_move.py`)
  picks the highest-value action, no model call required.
- **AI router**: `ai_router.py` implements the deterministic -> local ->
  cheap-cloud -> premium-cloud hierarchy and defaults to `SAVE_CREDITS`.
  No cloud calls are wired into the action registry yet -- Level 0
  actions are what's shipped today; Level 1+ hooks are ready to extend.
- **Workers**: `/api/workers` distinguishes DataBossX-owned processes
  (from our own registry) from merely-observed ones on the box, and
  refuses to stop anything not in the registry.
- **Receipts**: every action run writes a compact receipt row (task,
  inputs, output summary, files changed, rollback note).

## What's a stub, on purpose

- Local-model (Ollama) *usage* isn't wired into any action yet --
  `ai_router.detect_local_model()` only detects availability so the UI
  can show real status without pretending to call a model that isn't
  there.
- Voice intake, richer evidence explorer, background job scheduler UI,
  and phone-native app wrapping are Phase C per the build mission and
  are not implemented in this pass.

## Tests

```bash
cd command_center
python3 -m unittest tests.test_command_center -v
```
