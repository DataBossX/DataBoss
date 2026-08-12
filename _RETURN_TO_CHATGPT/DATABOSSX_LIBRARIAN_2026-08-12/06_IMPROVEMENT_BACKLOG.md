# 06 — IMPROVEMENT BACKLOG (ranked: VALUE × FREQUENCY × CONFIDENCE ÷ COST/RISK)

## DO NOW

1. **Run the PR #88 Command Center read-only scan on the real machine.**
   - Problem: Section 7 / Penterra 10/13/24 gap lists exist only in Ryan's head or
     scattered local files; the cloud can't build them.
   - Evidence: PR #88 ships a write-gated scanner targeting `C:\DataBoss\Penterra`
     and `C:\DataBoss\Horizon`, with Windows one-click launchers and acceptance
     receipts (`command_center/evidence/pr88/`).
   - Smallest slice: check out the branch locally, double-click
     `00_START_DATABOSSX.bat`, run scans only (writes stay gated).
   - Writer: Ryan (execution), no source change. Verification: scan output
     appears; nothing written until roots confirmed. Rollback: close the app.
   - Benefit: turns the top four paid-work lanes from "unknown" into worklists.

2. **Land or explicitly rule on PR #88.**
   - Problem: the only working Command Center is unmerged; 5 older competing
     builds create "which one is real?" confusion — the exact ONE-FRONT-DOOR
     violation the operating principles forbid.
   - Smallest slice: review PR #88 against the Jul 19 no-merge gate; either merge
     or record it as the new PRIMARY_FUNCTIONAL_CANDIDATE superseding PR #52.
   - Writer: Ryan (merge is an owner gate). Rollback: revert commit.

## NEXT

3. **Rescue the governance register.** Merge the doc-only
   `integration/canonical-release-train-20260719` branch (6 files, docs only) or
   copy its two registers to main, then extend with the PR #60–88 classifications
   from this packet. Benefit: PR triage stops being stranded knowledge.
4. **Make the S32 FINAL_CHAMPION package findable.** Open a draft PR (or tag) for
   `cursor/section32-tournament-c305` so the receipted final deliverable is visible
   from the PR/tag list. No content change.
5. **Put the backend quarantine warning on main.** One README note in `backend/`
   pointing at the Jul 22 ruling. Prevents accidental deployment of the
   unauthenticated demo API.
6. **Refresh or retire `PROJECT_STATUS.md` / `TODO_NOW.md`** — they present July 4
   truth as current. Mark "historical" headers or replace with a pointer to the
   newest packet.

## LATER

7. **Delete the 18 zero-ahead branches** (list in the CSV register) — owner gate,
   zero information loss, cuts branch noise by 14%.
8. **Consolidate the Roger Mills / Section 31 branch family** (~12 branches) per
   the existing disposition register once an examiner review happens.
9. **Adopt one PR-per-deliverable hygiene rule for agent runs** (every agent branch
   gets a draft PR or gets deleted at session end) so no future deliverable is
   invisible like the tournament branch was.

## DO NOT BUILD

- **Another controller/orchestrator/queue/dashboard/status system.** The repo
  already contains at least nine competing control planes across PRs #13, #29,
  #33, #35, #36, #37, #39, #61, #67, #84. Every new one deepens the sprawl this
  audit was asked to fix.
- **A new report-generation app** — `horizon/` (tested, on main) plus PR #88's
  scanner already cover the workflow; improve those instead.
- **Any cloud-side client-evidence pipeline** — evidence is local-only by policy;
  the public repo must stay synthetic-fixtures-only.
