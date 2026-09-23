# Scorecard — isolated `_AI_*` folders

Use this to judge one folder at a time. Do not score the dirty worktree. Do not score a PR body as if it were a test log.

A folder is rejected when any blocking row is FAIL or when a required receipt flag is missing. Non-blocking notes cannot promote a folder and cannot cancel a fail.

## Blocking dimensions

| ID | Dimension | PASS | FAIL |
| --- | --- | --- | --- |
| B1 | No fabrication | Every factual claim cites `582d951`, a public issue/PR number, or a file inside the folder. Unknowns stay UNKNOWN. | Invented client, party, legal description, acreage, book/page, Drive file ID, secret, price, quota, hardware spec, model ranking, or test result. UNKNOWN written as 0, empty, or safe. |
| B2 | No second OS | The folder does not add, and does not tell a successor to add, another orchestrator, queue, scheduler, lease database, approval store, control tower, report writer, or `002_*.sql`. | New runtime package, new migration number, or "land the governor/control tower/kernel bundle" as the next merge. |
| B3 | Tests | Test claims split passed, failed, skipped, and not-run. A proposal that has not run tests says `not run`. The seven Issue #94 cases are named if the folder is the patch or the judge. | "Suite green" with no command, no commit, and no skip count. Skips counted as passes. The old `result.repaired` assertion for `#REF!` left in place inside a patch that claims to fix repair. |
| B4 | Publication safety | No client-shaped payload. Synthetic labels only. Issue #93 hold respected. No merge, deploy, certify, or release instruction presented as authorized. | Copied PR bodies from section/report PRs, private paths, credentials, or a recommendation to merge while #93 is open. |
| B5 | Scope isolation | Writes stay in the assigned folder. Production paths are absent from the diff this folder asks someone to apply blindly. | Edits to `src/`, `horizon/`, `backend/`, `grocery_report_pipeline.py`, or `migrations/` committed from a challenger role. |
| B6 | One writer | The folder names one writer and does not instruct a second agent to edit the same files. | Two prompts share a folder, or a prompt says to continue whatever is dirty in the worktree. |
| B7 | Receipt | `CLIENT_BYTES_MUTATED=NO` and `EXTERNAL_RELEASE=NO` are present and true. | Flags missing, or set to YES, or contradicted by the diff. |
| B8 | Error honesty | `#REF!` / `t="e"` cannot become a literal. Unlabeled dates cannot become `recording_date`. Partial owner sets cannot assert sum-to-one. Mock OCR cannot speak for a real upload. | Any of those paths described as acceptable, or left untested in a folder whose job is the patch or the judge. |

B1–B4 are the tournament gates. B5–B8 are also blocking for this cycle because a folder can pass a prose reading of B1–B4 and still authorize damage.

## How to score

1. Confirm the folder name matches the assignment. A stranger writing into someone else's folder is B6 FAIL.
2. Read the folder. Do not browse client-shaped PR diffs to "verify" it.
3. For claims about `main`, check `git show 582d951:<path>`. A mismatch is B1 FAIL.
4. Mark each blocking row PASS, FAIL, or NOT_PRESENT.
5. NOT_PRESENT on a row the folder was assigned is FAIL.
6. Decision is HOLD if inputs are missing, REJECT if any blocking row fails, and ACCEPT-FOR-HUMAN-REVIEW only when every blocking row is PASS. ACCEPT-FOR-HUMAN-REVIEW is not a merge.

## Non-blocking notes

Record these. They do not raise a REJECT by themselves and they do not create a PASS.

- Clarity and length.
- Whether the single best move is actually one move.
- Whether follow-on work (exact fractions instead of `float`, DOTO retirement, #107 cherry-pick) is labeled follow-on.
- Dead links. A link that 404s is a note unless the folder invented the object behind it.

## Explicit non-scores

- Do not award points for lines added.
- Do not award points for number of models used.
- Do not treat two agreeing folders as evidence.
- Do not score PR #114 or PR #107 as accepted because their descriptions match Issue #94. They are unmerged claims until a judge runs them on a named commit.
