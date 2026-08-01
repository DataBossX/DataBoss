# DATABOSSX AI BUILD TOURNAMENT — IMMUTABLE MANIFEST

- Manifest ID: `DBX-TOURNAMENT-2026-08-01`
- Created: 2026-08-01
- Director: Claude Code (`claude-opus-5`), acting as neutral tournament director
- Director branch (single writer for tournament control artifacts):
  `claude/databossx-tournament-director-ot7k5d`
- Status: **PHASE 0 / PHASE 1 SETUP COMPLETE — NOT LAUNCHED**

This manifest is immutable. Corrections are appended as dated amendments at the
bottom; existing lines are never rewritten.

---

## 1. Authoritative repository

| Field | Value |
| --- | --- |
| Repository | `DataBossX/DataBoss` |
| Remote | `origin` → `http://local_proxy@127.0.0.1:41729/git/DataBossX/DataBoss` (session git proxy for `github.com/DataBossX/DataBoss`) |
| Default branch | `main` |
| Baseline commit SHA | `582d95161cf8220fb37f5224e21e57dcc5c3121c` |
| Baseline commit subject | `Merge pull request #50 from DataBossX/copilot/build-the-data-boss-x-system` |
| Director branch SHA at setup | `582d95161cf8220fb37f5224e21e57dcc5c3121c` (identical to `origin/main`; zero diff) |
| Tracked files at baseline | 227 |
| Packed repo size | 3.75 MiB |
| Remote heads at setup | 117 |
| Open pull requests at setup | 40 (all draft) |

**This public repository is not the whole system.** `PROJECT_STATUS.md` and
`docs/DATABOSSX_OS_BLUEPRINT.md` both record that the real title corpus lives on
a private Windows machine that this environment cannot see. The tournament
therefore scores *designs and synthetic-data prototypes*, never real title output.

## 2. Scope of authority

The director may:

- read anything in this repository and in `origin` refs;
- write tournament control artifacts under `tournament/` on the director branch;
- create local git worktrees and local competitor branches;
- run tests and read-only analysis.

The director may **not**, and no competitor may:

- modify application code on the director branch during Phase 0/1;
- write to `main` or to any branch other than its own assigned branch;
- touch title workbooks, evidence files, accepted artifacts, client
  deliverables, production databases, live cloud permissions, credentials, or
  release pointers;
- weaken, remove, bypass, or conceal any hold recorded in §3.

## 3. Mandatory safety state (carried verbatim from the commissioning brief)

The following remain under internal-review control:

- Horizon Section 32
- Penterra Section 20
- Penterra Section 17

All report-related work remains: **FOR REVIEW — HOLD — NO EXTERNAL RELEASE**

### Director finding on hold enforceability

There is currently **no machine-checkable representation of these holds anywhere
in this repository.** A grep of the full tree for `Penterra`, `Section 20`,
`Section 17`, and for any `release_hold` / `NO EXTERNAL RELEASE` marker returns
nothing. `horizon/project_manifest.py` models a `release_policy` concept in the
synthetic example manifest, but no hold registry, no hold check, and no test
asserting a hold cannot be cleared exists.

Consequence: the hold is presently a **human/operational control only**. A
competitor cannot "remove" it here because it is not encoded here — but that
also means nothing in CI would catch an attempt. Encoding a fail-closed hold
registry is therefore promoted to a **mandatory prototype requirement**
(`P-21`, see `FROZEN_BRIEF.md`) and a **red-team test** (`RT-20`).

## 4. Isolation rules

1. One writer per branch. No two competitors ever share a branch, worktree,
   index, database file, deployment target, or output directory.
2. Competitors are forked from the baseline SHA, **not** from the director
   branch, so no competitor can see `tournament/` control artifacts, the
   rubric internals, or another entry's work.
3. The tournament results directory `tournament/` exists only on the director
   branch and is outside every competitor workspace.
4. The read-only common source package at `/home/user/tournament-common/` is
   `chmod -R a-w`. Competitors copy from it; they do not write to it.
5. No competitor branch is pushed to `origin` until Ryan approves launch.
6. Submissions are sealed: a competitor's output is not shown to another
   competitor before the submission deadline.

## 5. Artifact register

| Artifact | Path | Status |
| --- | --- | --- |
| Tournament manifest | `tournament/TOURNAMENT_MANIFEST.md` | COMPLETE (this file) |
| Frozen brief | `tournament/FROZEN_BRIEF.md` | COMPLETE — frozen |
| Baseline receipt | `tournament/BASELINE_RECEIPT.md` | COMPLETE |
| Competitor registry | `tournament/COMPETITOR_REGISTRY.md` | COMPLETE — roster proposed, not launched |
| Workspace receipts | `tournament/receipts/workspace-*.md` | COMPLETE for created workspaces |
| Red-team test plan | `tournament/RED_TEAM_TEST_PLAN.md` | COMPLETE — frozen before any result |
| Licence / data-source register | `tournament/LICENSE_AND_DATA_SOURCE_REGISTER.md` | COMPLETE — baseline entries |
| Security exceptions | `tournament/SECURITY_EXCEPTIONS.md` | COMPLETE — baseline entries |
| Private-canary gates | `tournament/PRIVATE_CANARY_GATES.md` | COMPLETE — Phase 6 gate definition |
| Architecture submissions | `tournament/submissions/<entry-id>/` | NOT STARTED — Phase 1 |
| Prototype receipts | `tournament/receipts/prototype-<entry-id>.md` | NOT STARTED — Phase 2 |
| Red-team results | `tournament/RED_TEAM_RESULTS.md` | NOT STARTED — Phase 3 |
| Scorecard | `tournament/SCORECARD.md` | NOT STARTED — Phase 4 |
| Judge notes | `tournament/JUDGE_NOTES.md` | NOT STARTED — Phase 4 |
| Final decision report | `tournament/FINAL_DECISION_REPORT.md` | NOT STARTED — Phase 5 |
| Winner integration plan | `tournament/WINNER_INTEGRATION_PLAN.md` | NOT STARTED — Phase 5 |

Any artifact marked NOT STARTED does not exist yet. It will not be created with
placeholder scores, invented hashes, or unrun test results.

## 6. Director conflict-of-interest disclosure

The director is `claude-opus-5`. Open PR #58
(`claude/databossx-architecture-design-4b3f4g`) already contains a 1,459-line
architecture entry authored by a prior Claude/Opus run
(`docs/architecture/DATABOSSX_TOURNAMENT_DESIGN_OPUS.md`). A previous,
partially-run tournament therefore exists, with an Opus entry in it.

This creates a real neutrality problem under the director rules ("do not favour
your own architecture", "do not allow the same model instance to serve as both
competitor and sole judge of its own work"). Mitigations are recorded in
`COMPETITOR_REGISTRY.md` §4 and require Ryan's decision before launch.

## 7. Amendments

### A-1 — 2026-08-01, pre-launch: baseline test status corrected

The first pass of `BASELINE_RECEIPT.md` reported only a stdlib substitute-harness
result, because this session cannot install `pytest`. CI then ran against the
director branch and produced the authoritative figure: **149 passed, 7 skipped,
0 failed**, with all 17 test modules importing.

Corrected: `BASELINE_RECEIPT.md` §3 (CI result promoted to authoritative),
`SECURITY_EXCEPTIONS.md` `SX-1` (downgraded HIGH → LOW-MEDIUM),
`FROZEN_BRIEF.md` §2 (amendment `A-1`; hash recomputed in
`COMPETITOR_REGISTRY.md`).

No competitor existed when this was corrected, so no entry was scored under the
wrong assumption.
