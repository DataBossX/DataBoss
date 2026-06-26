# RogerMills_Title_Finisher — Final Claude Review Pass

Final landman-quality review (order 3, after Cursor and Codex) of the
**Roger Mills 31‑12N‑24W** title workbook. Produced 2026‑06‑26 in a Claude Code
cloud session.

## Contents
| File | What it is |
|------|------------|
| `outputs/03_CLAUDE_VERIFIED.xlsx` | **Verified candidate.** Source workbook with stale external links removed; all 20 tabs, formatting, embedded images, and comments preserved exactly. |
| `outputs/SOURCE_MAP_CLAUDE.csv` | 1,470 documents mapped: Book/Page → doc type → parties → legal → source file. |
| `QA_LOG_CLAUDE.md` | Checks run and results (chain balance, tie-out, links, wells, coverage). |
| `GAP_LIST_CLAUDE.md` | Open / Needs-Verification items — all true evidence gaps. |
| `CHANGELOG_CLAUDE.md` | What changed, what was deliberately not changed, and deferred edits. |
| `COST_LOG_CLAUDE.csv` | Run/cost log. |
| `source/Final_Updated_Title_Report.xlsx` | Source workbook (from Google Drive) used for this pass, kept for provenance. |

## How to read this
Start with `QA_LOG_CLAUDE.md` (verdict + checks), then `GAP_LIST_CLAUDE.md`
(what still needs a recorded-image pull), then `CHANGELOG_CLAUDE.md`.

## Important context
- This pass ran in a cloud session. The task's local Windows paths
  (`D:\Desktop\...`) and the `01_CURSOR_VERIFIED` / `02_CODEX_VERIFIED`
  intermediate files were **not reachable**; the review was performed as a single
  evidence pass against the real workbook on the operator's Google Drive (user
  approved). No three-way Cursor-vs-Codex diff was possible.
- **No recorded instrument images** were accessible, so every item whose
  resolution requires an image (net acres, full lease terms, depth/reservation
  language, HBP production) remains Open by necessity, not by oversight.
- Standing reviewer rules live in the repo-root `CLAUDE.md`.
