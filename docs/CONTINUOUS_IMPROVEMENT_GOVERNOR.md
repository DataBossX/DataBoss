# Continuous Improvement Governor

Public-safe implementation of [Issue #68](https://github.com/DataBossX/DataBoss/issues/68)
and the first executable slice of [Issue #69](https://github.com/DataBossX/DataBoss/issues/69).

This is not a second operating system, queue, ledger, or approval plane. It
extends the canonical `src/databossx` package and the existing SQLite project
database.

## Cycle

```text
OBSERVE → PROPOSE → PRIORITIZE → AUTHORIZE (L2) → TEST → RECEIPT → LEARN
```

A cycle is incomplete without a terminal receipt. The governor never auto-merges,
never mutates client bytes, never expands permissions, and never edits audit
history.

Autonomy ceiling here is **L2 isolated implementation**. L4 external release
remains a hard veto.

## Commands

```bash
PYTHONPATH=src python -m databossx census --repo-root .
PYTHONPATH=src python -m databossx policy-gate --repo-root .
PYTHONPATH=src python -m databossx tournament --repo-root .
PYTHONPATH=src python -m databossx cycle --repo-root .
```

## Isolated AI folders

Successor agents must write only to a unique `_AI_<MODEL>_<ROLE>__<YYYYMMDD>/`
folder. The tournament judge scores those folders and blocks client-shaped or
second-OS submissions.

## Related

- OS blueprint: [docs/DATABOSSX_OS_BLUEPRINT.md](DATABOSSX_OS_BLUEPRINT.md)
- Issue #94 integrity repairs landed in this same public-safe train
- Do not merge [PR #116](https://github.com/DataBossX/DataBoss/pull/116) as runtime
