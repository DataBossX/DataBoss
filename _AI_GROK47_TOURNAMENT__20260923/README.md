# Grok 4.7 challenger — DataBossX tournament 2026-09-23

This folder is an isolated strategy submission. It is not runtime, not a kernel, and not a merge candidate.

| Item | Value |
| --- | --- |
| Role | Challenger. Not the production writer. |
| Model | Grok 4.7 (SpaceXAI) |
| Baseline | `main` @ `582d95161cf8220fb37f5224e21e57dcc5c3121c` (2026-07-17 23:09 -0500) |
| Repo | https://github.com/DataBossX/DataBoss |
| This run | https://cursor.com/agents/bc-01a0cfc6-b693-7e4b-a80e-906ef0f67f1f |
| Prior challenger | https://cursor.com/agents/bc-01a0cf2a-59cf-72ac-8e08-3d6a3440b413 (PR #116) |
| Holds | Issue #94 open (P0 integrity). Issue #93 open (publication). Issue #68 open (governor). |

## Verdict

Land one synthetic-only fail-closed patch for the seven Issue #94 defects that are still on `582d951`. Do not land it from this folder. Do not merge PR #114 or PR #107 as the vehicle. Do not add another `002_*.sql` in the same cycle.

PR #116's best move (land the #107 router, cache, and receipts first) leaves workbook error downgrade, fabricated recording dates, missed ordinary decimals, and the unauthenticated mock-OCR backend on `main`. Those are the defects that can hide a bad value or invent one.

## How to read

1. `TOURNAMENT_SUBMISSION.md` — twelve required sections.
2. `BEST_PROMPTS.md` — copy-paste prompts. Each successor has its own folder.
3. `SCORECARD.md` — blocking pass/fail for any `_AI_*` folder.
4. `RECEIPT.md` — what this agent did, what it refused, and the freeze.

## What this folder refuses to be

- A second orchestrator, queue, database, or report writer.
- A certification, title opinion, or client deliverable.
- A price list or model leaderboard. Provider prices were not re-fetched here. PR #116's prices are not adopted.
- Proof that the dirty worktree on this cloud checkout is correct. That tree changed while this folder was written. `git show 582d951:<path>` is the baseline.
