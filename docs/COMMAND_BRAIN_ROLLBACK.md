# Command Brain Alpha — Rollback

The Command Brain is additive. Nothing in the existing DataBossX codebase was
modified except:

- `tests/conftest.py` — appended pytest fixtures, guarded so the file still
  imports when pytest is absent
- `README.md` — added documentation links
- `migrations/002_command_brain.sql` — new file, additive only

No existing module, table, or test was changed.

## Level 1 — turn it off without removing anything

Stop calling it. The Command Brain has no scheduler, no daemon, and no import
side effects: nothing runs unless something calls `CommandBrain.handle()` or
starts `server.serve()`. An unused package is inert.

## Level 2 — drop the schema

`002_command_brain.sql` creates only `cb_*` objects and declares **no foreign key
into the Phase-2 tables** from `001_initial_schema.sql`. Removing it cannot
orphan or cascade into existing data.

```sql
-- Triggers first: the append-only guards refuse the DROP TABLE otherwise.
DROP TRIGGER IF EXISTS cb_audit_no_update;
DROP TRIGGER IF EXISTS cb_audit_no_delete;
DROP TRIGGER IF EXISTS cb_receipts_no_update;
DROP TRIGGER IF EXISTS cb_receipts_no_delete;

DROP TABLE IF EXISTS cb_audit_events;
DROP TABLE IF EXISTS cb_receipts;
DROP TABLE IF EXISTS cb_memory_items;
DROP TABLE IF EXISTS cb_test_suites;
DROP TABLE IF EXISTS cb_human_review_queue;
DROP TABLE IF EXISTS cb_quarantine;
DROP TABLE IF EXISTS cb_holds;
DROP TABLE IF EXISTS cb_defects;
DROP TABLE IF EXISTS cb_artifacts;
DROP TABLE IF EXISTS cb_leases;
DROP TABLE IF EXISTS cb_lane_tokens;
DROP TABLE IF EXISTS cb_approvals;
DROP TABLE IF EXISTS cb_task_envelopes;
DROP TABLE IF EXISTS cb_task_drafts;
DROP TABLE IF EXISTS cb_judge_decisions;
DROP TABLE IF EXISTS cb_candidate_scores;
DROP TABLE IF EXISTS cb_tournament_candidates;
DROP TABLE IF EXISTS cb_tournaments;
DROP TABLE IF EXISTS cb_jobs;
DROP TABLE IF EXISTS cb_agent_assignments;
DROP TABLE IF EXISTS cb_agent_instances;
DROP TABLE IF EXISTS cb_agent_roles;
DROP TABLE IF EXISTS cb_model_capabilities;
DROP TABLE IF EXISTS cb_model_endpoints;
DROP TABLE IF EXISTS cb_model_providers;
DROP TABLE IF EXISTS cb_tool_invocations;
DROP TABLE IF EXISTS cb_tool_definitions;
DROP TABLE IF EXISTS cb_plan_steps;
DROP TABLE IF EXISTS cb_plans;
DROP TABLE IF EXISTS cb_intents;
DROP TABLE IF EXISTS cb_transcripts;
DROP TABLE IF EXISTS cb_voice_sessions;
DROP TABLE IF EXISTS cb_messages;
DROP TABLE IF EXISTS cb_conversations;
```

**Export the ledger first if you may need it.** The audit events and receipts are
the record of every decision the system made; dropping them is not reversible.

```sql
.mode json
.once command_brain_ledger_export.json
SELECT * FROM cb_audit_events ORDER BY id;
.once command_brain_receipts_export.json
SELECT * FROM cb_receipts ORDER BY created_at, receipt_id;
```

Verify the chain before you export, so you know whether what you are keeping is
intact:

```python
CommandBrainStore(db_path).verify_ledger()   # {"valid": True, ...}
```

## Level 3 — remove the code

```
git rm -r src/databossx/command_brain
git rm migrations/002_command_brain.sql
git rm tests/test_command_brain_*.py
git rm docs/COMMAND_BRAIN_*.md
```

Then revert the appended fixture block at the end of `tests/conftest.py` and the
documentation links in `README.md`.

`src/databossx/` (config, database, hashing, intake, models, orchestrator, api)
and `migrations/001_initial_schema.sql` are untouched by this work and keep
working on their own.

## Level 4 — revert the branch

```
git checkout main -- .
```

or close the pull request without merging. The branch
`claude/databossx-command-brain-alpha-gh8syu` contains only this subsystem.

## Verifying a rollback

```
python -m pytest -q                       # existing suites unaffected
python -c "import databossx; print(databossx.__version__)"
```

Expected after a full removal: the pre-existing baseline — 61 passing tests, with
`tests/test_grocery_pipeline.py::test_all_outputs_exist` failing and the
`test_horizon_*` modules erroring at collection, both due to optional third-party
packages missing in this environment. Neither is caused by, nor fixed by, the
Command Brain.

## What rollback does not undo

Nothing. The Command Brain wrote no client file, touched no production database,
activated no connector, modified no release hold, and made no external call. A
rollback removes a subsystem; it has no external effects to reverse.
