# 02 — INVENTORY AND CANONICAL MAP

Environment: cloud clone at `/home/user/DataBoss` (GitHub `DataBossX/DataBoss`),
HEAD `582d951`, branch `claude/databossx-librarian-audit-idbukq` (created for this
audit; identical to `origin/main` at start). Working tree clean. 227 tracked files.
Zero PDFs/XLSX/DOCX anywhere in the tree — the public repo carries **code and
synthetic fixtures only**, matching the Jul 19 governance baseline statement.

## Canonical (on main, verified)

| Artifact | Path | Status |
| --- | --- | --- |
| Horizon workbook-QA / controlled loop | `horizon/` (22 files) | Canonical; 146 tests pass |
| Grocery pipeline | `grocery_report_pipeline.py` + `tests/test_grocery_pipeline.py` | Canonical; tested |
| DataBossX foundation package | `src/databossx/` | Canonical (PR #50, Jul 17) |
| OCR image commander | `doto_image_commander/` | Canonical; Streamlit app |
| Docs/governance on main | `docs/DATABOSSX_OS_BLUEPRINT.md`, `docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md` | Canonical |
| Marketing website | `website/` | Canonical (PR #42) |
| Legacy demo backend | `backend/`, `frontend/`, `entrypoint.sh`, `nginx.conf` | Canonical-but-quarantine-ruled (see security note) — do not deploy |

## Likely canonical, stranded on branches (newest per family)

| Family | Likely canonical | Evidence | Where |
| --- | --- | --- | --- |
| Command Center | PR #88 `claude/databossx-working-command-center-6dq4ej` | Newest (Aug 10), working app + Windows launchers + acceptance evidence | unmerged |
| Section 32 final report | `cursor/section32-tournament-c305` FINAL_CHAMPION | Aug 6 receipt + SHA256SUMS + qualifications | unmerged, **no PR** |
| Governance / PR triage | `integration/canonical-release-train-20260719` | Full disposition register PRs 4–59 | unmerged |
| S32 current-data research | PR #85 `claude/section32-v10-current-data-w0hnr6` | Read-only packet, honest RESEARCH_BLOCKED | unmerged |
| Landman Helper | PR #54 `cursor/databossx-landman-helper-ecff` | Only implementation of that name | unmerged, Jul 18 |

## Duplicate / superseded groups (recommend-only; nothing deleted)

- **Command Center family (≥6 competing builds):** PRs #88, #66, #67, #52, #26, #34
  plus `claude/build-streamlit-command-center-*` ×2, `claude/horizon-command-center-vk3n1n`,
  `claude/databossx-working-command-center-6dq4ej`. Jul 19 register already ruled
  #52 primary — superseded in practice by #88 (newer, working, evidence-backed).
- **Roger Mills / Section 31 report family (~12 branches):** `claude/roger-mills-*`,
  `claude/section-31-*`, `claude/section31-*`, PRs #12/#16/#17/#20/#22/#24 — older
  client-lane work; register holds them at examiner-review gate.
- **Title-link extractor duplicates:** PR #7 vs PR #8 (near-identical, Jun 18).
- **Orchestrator/controller family:** PRs #13, #29, #33, #35, #36, #37, #39, #61,
  #84 — competing control planes; all donor-only per register logic.
- **18 fully-merged/empty branches** (0 commits ahead of main): all `copilot/*`
  design branches, `cursor/section32-controlled-loop-04fb`,
  `cursor/databossx-operating-system-9825`, `claude/doto-image-commander-BMEnu`,
  etc. — full list in `03_DUPLICATE_AND_CLEANUP_REGISTER.csv`. Safe branch-deletion
  candidates (owner action; nothing auto-deleted).

## Source folders / protected material

None present in this environment. All client evidence is local-machine only.
Nothing in this run touched, moved, or deleted any file outside the new
`_RETURN_TO_CHATGPT/DATABOSSX_LIBRARIAN_2026-08-12/` folder.

## Unknowns (honest)

- State of `C:\DataBoss` itself (repos, worktrees, dirty trees, local receipts).
- Whether local Command Center / Landman Helper installs exist and which version.
- Whether local Section 7 / Penterra packages are newer than anything referenced here.
- Private Drive/Dropbox roots named in S32 receipts (identified there, inaccessible).
