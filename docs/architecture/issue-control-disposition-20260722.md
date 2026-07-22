# DataBossX Issue Control Disposition — 2026-07-22

**Status:** Governance record only. This document does not authorize a merge, deployment, credential change, client release, workbook write, watcher launch, history rewrite, or destructive cleanup.

## Controlling open issues

| Issue | Role | Current disposition | Exit condition |
|---|---|---|---|
| #56 | Canonical public release-train control | **CONTROLLING** | One coherent integration branch; one persistence and control kernel; public security/CI gates; private Windows terminal canary; human release gate |
| #28 | Parent execution board | **OPEN / PARENT CONTEXT** | Close only after the release train, private runtime, project evidence, and human-release workstreams are reconciled into durable successor controls |
| #2 | Historical credential exposure | **OPEN / BLOCKED_EXTERNAL** | Redacted provider evidence proves revocation, usage review, least-privilege replacement where needed, runtime smoke test, old-key failure, and deployment/secret-store reconciliation |

## Superseded issues closed in this control pass

| Issue | Former instruction | Reason closed | Preservation result |
|---|---|---|---|
| #38 | Build on PR #36 as the integration candidate | Superseded by #56 and draft PR #57; PR #52 is now primary, PR #54 additive, and overlapping branches are donors | Issue history, donor branches, requirements, and test claims remain intact |
| #41 | Deploy PR #40 watcher and resume broad Section 32 processing/workbook repair | Unsafe under current private Windows, writer, source, and template gates; PR #40 is donor-only and Section 32 report/build writers remain frozen | Watcher branch, source history, and requirements remain intact; future use requires a new exact work order |

Both closures used GitHub's reversible `not_planned` state. No branch, commit, artifact, source, evidence, or issue history was deleted.

## Security incident status

Current-tree containment for issue #2 is verified only at the repository surface:

- `backend/.env` is absent from current `main`.
- A current-tree search returned no `zhipu` hit.
- `SECURITY.md` correctly treats every credential formerly committed in environment files as compromised.
- Current secret-scan workflows passing does not prove provider revocation, usage review, replacement deployment, or historical cleanup.

Issue #2 therefore remains open and assigned to the repository owner. Never place a credential value, connection string, token screenshot, full environment dump, or private receipt in a public issue.

## Agent routing rule

An agent reading an old issue, PR body, Drive document, branch name, filename, or generated prompt must compare it against this order:

1. Issue #56 and draft PR #57 for public repository governance.
2. Current private Drive controls for project/write authority.
3. The private Windows truth gate for local runtime identity and writer authority.
4. Exact hash-pinned, owner-verified work orders for bounded execution.

Conflicts resolve to **HOLD**, not to the newest timestamp, strongest filename, largest branch, or model consensus.

## Current no-action boundaries

Until the relevant gates pass:

- do not merge or rebase overlapping platform PRs;
- do not deploy PR #40 or another watcher;
- do not write a Section 32 report or template copy;
- do not rotate or create provider credentials without a secure destination and provider-console control;
- do not rewrite Git history;
- do not archive, delete, transfer, rename, change visibility, change default branches, or alter deployments for portfolio repositories;
- do not claim production readiness, title acceptance, client readiness, or release authority.
