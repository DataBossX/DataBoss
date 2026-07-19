# DataBossX Canonical Release Train — 2026-07-19

Status: **HOLD — governance branch only; no production merge authority**

Controlling issue: [#56](https://github.com/DataBossX/DataBoss/issues/56)  
Parent execution board: [#28](https://github.com/DataBossX/DataBoss/issues/28)

## Baseline

- Repository: `DataBossX/DataBoss`
- Default branch: `main`
- Verified baseline commit: `582d95161cf8220fb37f5224e21e57dcc5c3121c`
- Merged foundation: PR #50
- Integration branch: `integration/canonical-release-train-20260719`

The public repository contains code and synthetic fixtures only. Real client evidence, private runtime state, project workbooks, private manifests, credentials, private hashes, job queues, and release receipts do not belong in GitHub.

## Candidate ruling

| Rank | Candidate | Disposition |
|---:|---|---|
| 1 | PR #52 — Command Center | Primary functional candidate. Keep draft. Port bounded slices only after the private Windows truth gate. |
| 2 | PR #54 — Landman Helper | Additive candidate. Rebase or selectively port onto the release train after the primary slice passes. |
| 3 | PR #51 — Trusted kernel/economics | Donor only. Require schema, API, migration, and control-kernel compatibility analysis before selective reuse. |
| 4 | PR #55 — Stage 0 audit/artifacts | Donor only. Current workflows require action; restore green CI before reuse. |
| 5 | PR #35 — Multi-AI watcher foundation | Phase 0 donor only. Reuse selected schemas, validation patterns, atomic claims, and tests—not the branch as a production dispatcher. |

## No-merge gate

No candidate may be merged or promoted until all of the following are independently proven:

1. The actual private Windows repository, worktrees, remotes, branches, nested repositories, dirty state, unpushed commits, and active writers are preserved and reconciled.
2. One persistence model is selected with versioned migrations, rollback, and no competing source of truth.
3. One task, lease, approval, artifact-lineage, and append-only audit implementation is selected.
4. Full tests, security scan, publication-policy gate, dependency review, path/reparse protections, formula-injection protections, replay/idempotency, timeout/cancel/restart, and audit verification pass.
5. A public synthetic-fixture pipeline passes without private data.
6. A private Windows end-to-end canary returns a terminal receipt with immutable input/output hashes, restart recovery, and no duplicate execution.
7. Human review remains mandatory for client release and evidence-dependent title conclusions.

## Integration sequence

1. Preserve and reconcile the private Windows state. Do not reset, checkout, merge, rebase, or cherry-pick before preservation.
2. Start from this branch and port the smallest coherent PR #52 slice.
3. Run all gates and record the exact commands, exit codes, and artifact hashes.
4. Port PR #54 only after its database, workflow, API, UI, and artifact contracts are reconciled with the selected architecture.
5. Port selected PR #51, #55, and #35 capabilities only with focused tests and source-PR provenance.
6. Keep every slice reversible and independently testable.
7. Open a dedicated draft integration PR only after the branch contains a coherent tested slice.

## Definition of done

- One coherent architecture exists on one integration branch.
- One persistence, task, lock, approval, and audit model is documented and tested.
- Full CI and private Windows canaries pass.
- No private/client material exists in Git history or CI artifacts.
- Superseded branches receive explicit donor/archive dispositions.
- Final merge remains a separate reviewed action.
