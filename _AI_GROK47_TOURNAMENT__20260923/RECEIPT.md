# Receipt — Grok 4.7 challenger — 2026-09-23

## Identity

- Folder: `_AI_GROK47_TOURNAMENT__20260923/`
- Agent: Grok 4.7 challenger (SpaceXAI)
- Parent run: https://cursor.com/agents/bc-01a0cfc6-b693-7e4b-a80e-906ef0f67f1f
- Prior tournament inspected via metadata and PR #116: https://cursor.com/agents/bc-01a0cf2a-59cf-72ac-8e08-3d6a3440b413
- Baseline commit: `582d95161cf8220fb37f5224e21e57dcc5c3121c`
- Level: L0 observe, L1 draft proposal
- Decision: HOLD on merge. Single proposed move is the Issue #94 fail-closed patch in a separate Codex folder.

## Flags

CLIENT_BYTES_MUTATED=NO
EXTERNAL_RELEASE=NO
P10_SUCCESSOR_CREATED=NO
AUTO_MERGE=NO
DRIVE_ACCESSED=NO
TESTS_EXECUTED=NO
UNKNOWN_IS_NOT_ZERO=YES
PRODUCTION_PATHS_EDITED_BY_THIS_AGENT=NO

## Evidence used

- `git show 582d951` for `horizon/repair.py`, `grocery_report_pipeline.py`, `backend/server.py`, `tests/test_horizon_repair_orchestrator.py`, `src/databossx/`, `migrations/`
- Blob hashes: repair `c889a125732bf6b95920959d88f17fe57b2b23f0`, grocery `a5d0e440aa5dbbd1e8a86d40541c160b0b822dfc`, server `351c6fce641c65d4dc4e0d5e03f8794c08eafc99`
- Issues #94, #68, #93 and open PR list (24 open, 18 draft, 6 not draft)
- PR metadata for #114, #116, #110, #107
- `docs/DATABOSSX_OS_BLUEPRINT.md`, `docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md`
- A point-in-time look at an untracked `migrations/002_governor.sql` header and `src/databossx/governor/` filenames in this checkout

## Evidence not used

- Drive and the private Windows control root
- Provider price pages
- PR branch checkouts
- pytest
- GitHub branch-protection settings
- Full transcripts of either cloud agent
- Bodies of section-shaped pull requests

## Self-critique

Attack 1. "You told Codex to rewrite the backend, which is a second API."
Disposition: the allowlist is the existing legacy file plus a guard it calls, so the demo server stops failing open. The prompt forbids a new app, a migration, and a governor. B2 stands.

Attack 2. "Rejecting #114 and #107 leaves the defects unfixed."
Disposition: the best move is the fix, isolated. The rejection is of the bundles and of merging. The defects stay listed as open on `582d951`.

Attack 3. "You observed a dirty governor and then specified another governor."
Disposition: section 6 is a folder-only envelope with scores forced to UNKNOWN. It tells successors not to commit `002_governor.sql`. No table is created by this folder.

Attack 4. "Citing Acme Minerals and Client ABC fabricates parties."
Disposition: both strings are already in public `main` source. The receipt marks them as fixtures. Successor prompts forbid copying them into new data and require `SYNTHETIC-OWNER-*`.

Attack 5. "24 open PRs / 6 not-draft may have gone stale."
Disposition: those counts are labeled as of the `gh pr list` call in this run. They are not a live guarantee. A later census must re-count. Unknown drift is not zero.

Attack 6. "You did not run the seven tests, so the defect description could be wrong."
Disposition: the defect statements follow the source text: `recover=True`, deletion of `<f>` and `t="e"`, `parse_date` fallback, `\\d{4,9}`, no auth dependency, wildcard CORS with credentials, `0.0.0.0`, mock OCR string. Runtime exploit success is explicitly UNKNOWN. Tests are `not run`.

Attack 7. "The committed test already expects repair to refuse."
Disposition: `git show 582d951:tests/test_horizon_repair_orchestrator.py` asserts `result.repaired` on the `#REF!` fixture. The worktree copy differed during the run and is not the baseline.

Attack 8. "Cherry-pick from #114 smuggles the kernel."
Disposition: move 20 allows a human to take the three defect files only after the judge compares behavior. The rest of the 37-file PR stays out. If the files are entangled, the judge FAILs B2 and the cherry-pick stops.

Attack 9. "Folder names collide with the orchestrator assignments."
Disposition: successor folders are `_AI_CODEX_FAILCLOSED_PATCH__20260923/`, `_AI_CLAUDE_JUDGE_ISSUE94__20260923/`, `_AI_GPT_PR_CLASSIFICATION__20260923/`, `_AI_GEMINI_SYNTHETIC_PACK__20260923/`, `_AI_GROK_VETO_SCORE__20260923/`. Occupied names are listed as forbidden.

Attack 10. "HOLD versus PROPOSE is a mixed decision."
Disposition: HOLD is the merge decision. PROPOSE is the only authorized next artifact. The receipt says both so a reader cannot treat the essay as a green gate.

Attack 11. "You certified #107's quality floats and certified that the whole test suite locks in the bug."
Disposition: fixed before freeze. #107's floats are attributed only as PR #116's claim. The repair test is described as one assertion (`result.repaired`), not as a suite run.

Attack 12. "The commit date disagrees with a UTC 'July 18' reading."
Disposition: the baseline timestamp is `2026-07-17 23:09 -0500` from `git log`. No second date is claimed.

## Commit-time observation

The argument above was written against `main` @ `582d95161cf8220fb37f5224e21e57dcc5c3121c`, which was still `origin/main` when this folder was committed. During the write, the shared worktree moved off `cursor/kernel-governor-tournament-7f1f` onto `cursor/simplify-governor-public-safe-7ac3` at `e336b8f9334d6d660e180b8f31a7699a2ea17c40`. That HEAD is a descendant of `582d951`. Its commit messages mention Issue #94 and a governor. This agent did not review those commits. A commit message is not a closed defect. `582d951` remains the baseline, and those later commits stay UNREVIEWED.

## Freeze

FROZEN=YES
Critique attacks 1–12 were applied or answered in this folder before this line.
The commit-time observation above is the last edit.
This file and the four siblings are the challenger submission.
Further production edits in the shared checkout are not part of this receipt.
