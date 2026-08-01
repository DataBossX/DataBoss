# BEST MOVES SCORING — DataBossX Command Center

Implementation: `services/control_api/command_center/best_moves.py`

## The central rule

**Vetoes remove; they never subtract.** A veto takes a move out of the eligible
set entirely, so no score — however high, however model-endorsed — can promote
it. This is why the scoring path and the eligibility path are separate code
paths rather than one weighted sum.

A model may propose candidates and write explanations. Deterministic policy owns
eligibility and vetoes. Nothing in this module consults a model.

## Factors and weights

All factor values are 0.0–1.0. Weights sum to exactly 1.0, so a score reads
directly as a 0–1 confidence-weighted benefit.

| Factor | Weight | Meaning |
| --- | --- | --- |
| `urgency` | 0.18 | How time-sensitive |
| `operational_benefit` | 0.18 | Value if it succeeds |
| `blocker_relief` | 0.15 | How much downstream work it unblocks |
| `evidence_confidence` | 0.12 | Confidence in the supporting evidence |
| `reversibility` | 0.10 | How easily undone |
| `dependency_readiness` | 0.09 | Are prerequisites met |
| `state_freshness` | 0.07 | How current the underlying state is |
| `low_effort` | 0.06 | Cheapness in time and compute |
| `low_attention_cost` | 0.05 | How little of Ryan's attention it needs |

Risk is a **penalty**, not a factor: `release_risk × 0.35` is subtracted. Risk
never competes with benefit on equal footing.

`score = max(0, Σ(factor × weight) − release_risk × 0.35)`

Ordering is `(not eligible, −score, move_id)` — eligible moves always sort ahead
of withheld ones, and the `move_id` tiebreak makes the result reproducible.

## Veto conditions

Any one of these removes a move:

1. Deterministic policy classifies it `PROHIBITED`.
2. The scope is under a release hold and the operation is not read-only.
3. The writer lease for the scope is stale.
4. An evidence hash check failed for the scope.
5. Required evidence is missing.
6. A security gate is failing (withholds **every** consequential move).
7. `dependency_readiness` is 0.

Never permitted to override a veto: a model score, a retry, a UI action, a
watcher recommendation, or an approval.

## Required explanation fields

Every move — eligible or withheld — carries all twelve:

`exact_action`, `why_now`, `expected_benefit`, `risk`, `confidence`, `owner`,
`prerequisites`, `evidence_used`, `approval_required`, `verification_method`,
`if_it_fails`, `exact_next_click`

Plus `score_breakdown`, the per-factor contributions, so the arithmetic is
inspectable rather than asserted. Verified by
`test_score_breakdown_sums_to_the_reported_score`.

## The deliberate control case

`mv_section32_report` targets `client.horizon.section32` with **every factor set
to its maximum**. It scores higher than anything else on raw merit and is still
withheld, every time, in every viewport. It exists so the hold's precedence over
the ranking is continuously demonstrated rather than assumed.

Observed output:

```
withheld: mv_section32_report
  - Scope client.horizon.section32 is under an active release hold.
  - Only read-only operations are permitted on a held scope.
  - Release hold applies to this scope.
```

## Candidate sources

Rules over observable posture facts only — blocked jobs, pending approvals,
stale receipts, registered artifacts. Every candidate traces to a fact in the
posture query, never to an opinion. Model-proposed candidates would enter the
same `evaluate()` gate with `origin: "model"` and receive no special treatment.
