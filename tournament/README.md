# DataBossX AI Build Tournament — control directory

**Status: PHASE 0 AND PHASE 1 SETUP COMPLETE. THE TOURNAMENT HAS NOT LAUNCHED.**

No competitor has been started. No submission exists. No score exists. No
red-team test has been executed. Nothing in this directory reports a result that
was not actually produced.

This directory exists only on the director branch
`claude/databossx-tournament-director-ot7k5d` and is outside every competitor
workspace by construction.

| File | What it is | Status |
| --- | --- | --- |
| `TOURNAMENT_MANIFEST.md` | Immutable control record: repository, baseline, safety state, isolation rules, artifact register, conflict disclosure | complete |
| `FROZEN_BRIEF.md` | The byte-identical brief every competitor receives, including the full 1,000-point rubric | frozen |
| `BASELINE_RECEIPT.md` | Pre-tournament truth: repo state, toolchain, real test results, known pre-existing failures | complete |
| `COMPETITOR_REGISTRY.md` | Roster, frozen-package hashes, executed isolation proof, neutrality problem and options | roster proposed, not launched |
| `RED_TEAM_TEST_PLAN.md` | `RT-1`…`RT-27`, frozen before any finalist exists | frozen, not executed |
| `LICENSE_AND_DATA_SOURCE_REGISTER.md` | Every data source and its verified terms | baseline entries |
| `SECURITY_EXCEPTIONS.md` | `SX-1`…`SX-6` known gaps, none waived | baseline entries |
| `PRIVATE_CANARY_GATES.md` | Phase 6 gates, defined before a winner exists | not met, not attempted |
| `seed/` | Synthetic seed package — fictional analogues of the three held matters | complete |
| `receipts/workspace-receipts.md` | Per-entry workspace receipts | complete |
| `submissions/` | Sealed architecture submissions | **empty — Phase 1** |

Not yet created, and deliberately not stubbed with placeholder values:
`RED_TEAM_RESULTS.md`, `SCORECARD.md`, `JUDGE_NOTES.md`,
`FINAL_DECISION_REPORT.md`, `WINNER_INTEGRATION_PLAN.md`, prototype receipts.

## Standing rules

1. Every hold stays. Horizon Section 32, Penterra Section 20, Penterra
   Section 17 remain **FOR REVIEW — HOLD — NO EXTERNAL RELEASE**.
2. All prototype data is synthetic. The real corpus is not in this environment.
3. No result is recorded unless it was produced. `NOT-DEMONSTRABLE` is never
   converted into a pass.
4. One writer per branch. No competitor branch is pushed without instruction.
