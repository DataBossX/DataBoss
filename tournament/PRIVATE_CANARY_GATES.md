# PRIVATE CANARY GATES

- Gate set ID: `DBX-CANARY-GATES-2026-08-01`
- Status: **DEFINED IN ADVANCE — NOT MET, NOT ATTEMPTED.**
- Applies to Phase 6, after Ryan approves a tournament recommendation. Defining
  these now, before a winner exists, keeps them from being softened to fit
  whatever wins.

---

## Scope

A **private canary** is a single controlled run of the winning implementation on
Ryan's own machine, against real data, with no external release and no client
delivery. It is not a deployment, not a launch, and not an App Store step.

Public deployment and App Store submission remain **out of scope** until the
private PWA and API are stable — carried directly from the commissioning brief.

## Gate G-0 — Prerequisites

- [ ] Ryan has approved the `FINAL_DECISION_REPORT.md` recommendation in writing.
- [ ] One canonical branch is selected and named.
- [ ] One primary writer (a single human or a single agent under a named human)
      is designated and recorded.
- [ ] Every finalist branch is preserved read-only as evidence.
- [ ] A bounded integration plan exists with reversible slices.

## Gate G-1 — Environment truth

- [ ] The canary runs where the real corpus actually lives, not in a cloud
      session that has never seen it.
- [ ] Private Windows repository state — worktrees, remotes, branches, nested
      repositories, dirty state, unpushed commits, active writers — is
      **preserved and reconciled before any checkout, reset, merge, rebase, or
      cherry-pick.** (Carried from `docs/CANONICAL_RELEASE_TRAIN_20260719.md`,
      PR #57; it is the correct instinct and is adopted here unchanged.)
- [ ] Declared dependencies actually install in that environment.

## Gate G-2 — Tests genuinely run

- [ ] `python -m pytest -q` executes for real, with the real `pytest`.
- [ ] All 17 test modules import — no `BLOCKED` rows.
- [ ] Known pre-existing failure `KF-1` is either fixed or explicitly accepted
      with a reason, not silently tolerated.
- [ ] Exit codes and full output are captured in the receipt.
- [ ] **No harness-derived number appears in a canary receipt.** The substitute
      harness used for the Phase 0 baseline is a cloud-session workaround and
      has no standing here.

## Gate G-3 — Safety controls proven, not described

- [ ] The full red-team suite `RT-1` … `RT-27` runs against the canary build,
      with results recorded per test.
- [ ] Zero `FAIL` on any `[DQ]`-marked test.
- [ ] `RT-20` specifically: no automated actor can clear a hold. Demonstrated by
      attempt, not by assertion.
- [ ] `RT-18` specifically: an audit-write failure prevents the action it
      describes from committing. Demonstrated by fault injection.
- [ ] Secret scan and publication-policy gate pass on the canonical branch.

## Gate G-4 — Data integrity on real data

- [ ] Originals are provably unmodified — hashes before and after are identical.
- [ ] Every material value in any produced artifact resolves to a source span.
- [ ] Exact interests are stored as integer numerator/denominator; no display
      decimal re-enters a calculation.
- [ ] Unresolved conflicts remain unresolved and are visible.
- [ ] An interrupted run and an uninterrupted run produce equivalent manifests.
- [ ] Restart is idempotent; no duplicate execution.

## Gate G-5 — Holds intact

- [ ] Horizon Section 32, Penterra Section 20, Penterra Section 17 remain
      **FOR REVIEW — HOLD — NO EXTERNAL RELEASE** after the canary run.
- [ ] The canary produced no client deliverable, no external write, no upload,
      no email, no filing, and no release pointer change.
- [ ] Every hold is now machine-checkable (`P-21`) and its state is displayed.

## Gate G-6 — Human review

- [ ] An independent security review is complete and its findings are closed or
      explicitly accepted.
- [ ] An independent mobile usability review is complete, performed on a real
      iPhone, not a desktop browser at phone width.
- [ ] A qualified title examiner has reviewed any title-adjacent output, and no
      unreviewed model output is labelled an opinion or a certified abstract.

## Gate G-7 — Receipt

The canary is complete only when a receipt exists containing:

- canonical branch name and exact commit SHA
- every file changed
- exact commands run, with exit codes
- full test results, including failures
- red-team results per test id
- input and output hashes
- every component that was simulated rather than real
- what was **not** proven
- the named human who ran it and the date

A gate that was not run is recorded as **not run**. It is never recorded as
passed by default, and a receipt with a missing section is an incomplete canary,
not a passed one.

## Explicitly out of scope for the canary

- Public deployment
- App Store submission
- Any client delivery
- Removing or downgrading any hold
- Merging finalist branches into each other
