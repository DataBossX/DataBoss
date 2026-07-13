# Best Moves — executed and queued (2026-07-13)

This report executes every "best move" that is possible in a cloud checkout and
queues, with exact instructions, the moves that only the operator can take.
Authority for what counts as a best move: `docs/DATABOSSX_OS_BLUEPRINT.md`
§"Next operator action", `SECURITY.md`, `TODO_NOW.md`, and
`docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md`.

## 1. Verified in this session (done)

| Check | Result |
| --- | --- |
| Full repository test suite (`python -m pytest tests/`) on current `main` (5aba3eb) | **143 passed, 3 skipped** |
| `grocery_report_pipeline.py --self-test` (synthetic corpus, stages A–I) | **PASS** — 8 docs, 8 with text, 8 fact records, 1 duplicate, 4 red / 6 yellow issues surfaced as designed |
| Required deps to run the suite | `pydantic`, `openpyxl` (+ `pytest`); `horizon/requirements.txt` covers the rest |
| PR #26 merge blocker analyzed | Conflicts with `main` in **one file only: `.gitignore`** (both branches extended it). Resolution is a trivial union of both ignore lists. |
| PR mergeability snapshot | #23 clean · #24 clean · #26 **dirty** (.gitignore) · #29 clean · #25/#32/#33/#34/#35/#36 draft |

Conclusion: the machinery on `main` is healthy. Nothing on `main` blocks the
blueprint sequence. The bottleneck is **PR-backlog consolidation and the
operator-only actions**, not code health.

## 2. Open-PR triage (10 open PRs, ranked)

The blueprint's rule: one canonical engine, no competing authorities, security
first, evidence over synthesis. Applied to the backlog:

| PR | State | Recommendation | Why |
| --- | --- | --- | --- |
| **#26** Title Factory | open, conflicted (.gitignore only) | **Merge first** (after 1-file rebase) | Blueprint explicitly names it the canonical vertical slice ("Review and merge PR #26"). The only conflict is `.gitignore`; rebasing the branch on `main` and unioning the ignore lists clears it. |
| **#32** Publication-policy gate | draft | **Promote + merge second** | Directly implements SECURITY.md's "run secret and publication-policy checks before every merge" and hardens the PR #31 containment. Small, read-only, fail-closed. |
| **#29** Control plane | open, clean | **Review third — merge only what doesn't duplicate #26/#36** | Overlaps Phase 2 trusted kernel. Its secret-scan CI and workbook atomic-update pieces are valuable; its ledger competes with #36's kernel. Salvage, don't double-merge. |
| **#36** Secure orchestration + kernel | draft | **Operator decision: this OR the #26→#29 path, not both** | It *incorporates* #26 and adds the Phase 2 kernel. Choosing #36 makes #26/#29/#33 redundant; choosing #26-first makes #36 a rebase candidate. Two merged kernels = the "second title authority" the blueprint forbids. |
| **#33** Title Intelligence foundation | draft | **Close after kernel choice** | Third competing foundation (RBAC/auth/kernel). Redundant with #36 and #29. Harvest its RBAC + path-control tests if desired. |
| **#34** Drive command-center watcher | draft | **Hold (Phase 5)** | Well-gated but belongs to the DOTO/Drive migration phase; premature before the kernel exists. |
| **#35** Multi-AI fire watcher | draft | **Hold or close (Phase 4+)** | Multi-agent control plane; blueprint says model agreement is not evidence and connectors come after the proven core. Author itself says do not merge. |
| **#25** Horizon report generator | draft | **Close** | Blueprint verbatim: "do not merge PR #25 as a competing engine." Harvest export/Drive adapter ideas only. |
| **#24** Roger Mills S31 workbook fix | open, clean | **Do not merge to public repo — move to private storage, then close** | It commits a real client workbook, audit JSON with real owner names, and cell-level client data to the public repo. This violates `docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md` and the PR #31 containment. Note: the PR *description* already exposes client names publicly — consider editing it as part of incident containment. |
| **#23** Land Intelligence chaining app | open, clean | **Close** | Fourth competing engine (Streamlit + CrewAI, Roger Mills-specific). Its Decimal-exact verifier concepts already exist in `horizon/`. |

Net effect if followed: 10 open PRs → 1 merged (#26), 1 small gate (#32), 1
partial salvage (#29), 1 decision (#36), 6 closed/held.

## 3. Operator-only moves (queued — cannot be done from a cloud checkout)

In order, per the blueprint:

1. **Rotate every credential referenced by `SECURITY.md`** (`backend/.env` was in
   Git history; deletion did not revoke anything). Nothing else should merge
   ahead of this.
2. **Resolve PR #26's `.gitignore` conflict and merge it** (union both ignore
   lists; no code conflicts exist).
3. **On the Windows machine with the real Section 32 corpus** run PR #26's
   setup, tests, and inventory only; review the source manifest before
   allowing OCR/extraction.
4. **Edit PR #24's public description and disposition its client artifacts to
   private storage** (publication-policy containment).
5. Grocery Report path (if still live after July 6): run
   `py grocery_report_pipeline.py --root "D:\DataBoss\DataBossX_Final_Modular"`
   and work `output/review_required.csv` red rows first (see `RUNBOOK.md`).

## 4. What was deliberately NOT done here

- No PRs were merged or closed: merge/close decisions on other people's PRs and
  the #26-vs-#36 kernel choice are operator calls (and two of them are
  irreversible public-facing actions).
- No credentials touched: rotation must happen at the providers.
- No real title data processed: the corpus is not, and must not be, in this
  environment.
- No new engine code written: the backlog's problem is too many engines, not
  too few.
