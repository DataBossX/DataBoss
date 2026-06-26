# CLAUDE.md — Landman Title-Review Finisher Rules

Final landman-quality reviewer rules for the **Roger Mills 31‑12N‑24W** title
workbook (and future title-finisher passes). This file encodes the standing
review contract. Read it before touching any title workbook in this repo.

## Role & order of operations
- This is the **final review pass** after Cursor (`01_CURSOR_VERIFIED`) and
  Codex (`02_CODEX_VERIFIED`). Output is `03_CLAUDE_VERIFIED.xlsx`.
- Compare Cursor and Codex against **actual evidence**, not against each other.
  Choose **source‑supported truth only**. When the two disagree and neither is
  supported by an accessible source, keep the item **Open / Needs Verification**
  with a short reason — do not pick a side to look finished.
- **Never overwrite the final all‑three‑verified report.**

## Hard constraints (never violate)
1. **Do not add, delete, rename, or reorder worksheet tabs.**
2. **Preserve template formatting exactly.** Preserve embedded images, cell
   comments, drawings, merged cells, and formulas. Programmatic editors
   (openpyxl, pandas) silently drop embedded media/comments on save — if you
   must edit the binary, edit the underlying XML surgically and re‑validate, or
   defer the edit and document it.
3. **No new colors** except **yellow** highlights on critical documents.
4. **Do not invent facts.** No fabricated net acres, dates, royalties, or
   ownership. Index/snippet ≠ instrument: an index row only supports the index
   facts, never the full instrument terms.
5. Keep unresolved items as **Open** or **Needs Verification** with a short
   reason note.

## Verification checklist (every pass)
- **Tract sheets:** each includes all applicable mineral‑conveyance‑type
  documents (patents, mineral deeds, quit‑claim mineral deeds, decrees affecting
  minerals, trustees' mineral deeds).
- **WI sheets:** each includes all applicable leases, assignments, royalty,
  operating‑interest, working‑interest, and depth documents.
- **Depth‑limited rights** are separated where the source supports it (wellbore‑
  only, formation/depth severances). Do not infer a depth limit not in evidence.
- **Title sheet ties out** to the tract sheets and the WI sheets.
- **Overview / map** covers every tract; every aliquot of the section is either
  assigned to a tract or explicitly flagged unassigned.
- **All wells** are researched (OCC RBDMS / OTC) and cleaned.
- **Preserve** reservations, exceptions, depth clauses, NPRI, royalty
  reservations, term interests, life estates, trust issues, probate gaps, lease
  issues, HBP issues, pooling/spacing issues, and title defects. These never get
  dropped to make the report look clean.
- **Merge duplicates. Fix links.** Remove stale/orphaned external links.
- **Condense AI‑looking notes** into concise title notes — but never at the cost
  of a specific fact (Book/Page, date, party, fraction).

## QA loop
- Run all QA scripts. Add any missing checks.
- Loop until **no high‑severity errors remain**, or every remaining issue is
  documented as a **true evidence gap** (item that cannot be resolved without a
  recorded instrument image the reviewer cannot access).

## Required output artifacts (per pass)
- `outputs/03_CLAUDE_VERIFIED.xlsx`
- `QA_LOG_CLAUDE.md`, `GAP_LIST_CLAUDE.md`, `CHANGELOG_CLAUDE.md`
- `SOURCE_MAP_CLAUDE.csv`, `COST_LOG_CLAUDE.csv`

## Environment note
The canonical source files live on the operator's local machine
(`D:\Desktop\DataBossX\RogerMills_Title_Finisher`, `D:\Desktop\Database`,
`D:\Desktop\Horizon\Roger Mills`). When this review runs in a cloud session,
those paths are unreachable; pull the workbook and notes from Google Drive
instead, and write outputs to the repo / Drive (not `D:\`). State the
substitution plainly in the changelog.
