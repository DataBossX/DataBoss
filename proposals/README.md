# /proposals — self-improvement is proposal-only

Any agent (or human) that wants to change code that already passes its tests
does **not** edit that code directly. It writes a proposal here:

```
proposals/
  2026-07-11_short-slug/
    PROPOSAL.md      # what, why, risk, rollback plan, test plan
    changes.diff     # unified diff of the proposed change
```

Rules (from the DataBossX operating rules):

1. Proposals are markdown plus a diff. Nothing else.
2. Proposals are **never auto-merged**. A human reviews, applies, and runs the
   test suite before any proposal lands.
3. A proposal that touches passing code must state which tests cover the
   affected behavior and how the change keeps them green.
4. Proposals never contain secrets, credentials, or generated keys.

To apply a reviewed proposal:

```powershell
git apply proposals/<dir>/changes.diff
pytest foundry/tests
```
