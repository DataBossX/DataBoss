"""Independent judge layer.

Two rules make this a judge rather than a rubber stamp:

1. **Independence.** The agent that produced a candidate may not be the sole
   judge of it. Presenting the same model as both raises rather than warning.
2. **Evidence.** Every decision cites the specific score, delta, or hallucinated
   cell it rests on. A decision with no evidence refs fails its own schema.

The decision function itself is deterministic. A model may be asked to *explain*
a decision; it is never asked to *make* one.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import CommandBrainError
from .schemas import JUDGE_DECISION_SCHEMA, validate
from .scoring import ScoreCard, compare

#: Improvement smaller than this is noise, not a reason to replace a baseline.
MINIMUM_MEANINGFUL_DELTA = 0.01

#: When this share of reconciliation rows or more still needs a person, accepting
#: an automated reading is not a meaningful decision — a human makes it instead.
HUMAN_REVIEW_ROW_SHARE = 0.75


class IndependenceViolation(CommandBrainError):
    code = "INDEPENDENCE_VIOLATION"


@dataclass(frozen=True)
class JudgeDecision:
    candidate_id: str
    decision: str
    rationale: str
    evidence_refs: tuple
    blocking_regressions: tuple
    judge_model_id: str
    judge_role_id: str = "JUDGE"
    comparison: dict = None

    def to_dict(self) -> dict:
        payload = {
            "decision": self.decision,
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
            "blocking_regressions": list(self.blocking_regressions),
        }
        validate(payload, JUDGE_DECISION_SCHEMA, "$judge_decision")
        return payload

    def full_record(self) -> dict:
        record = self.to_dict()
        record.update(
            {
                "candidate_id": self.candidate_id,
                "judge_model_id": self.judge_model_id,
                "judge_role_id": self.judge_role_id,
                "comparison": self.comparison or {},
            }
        )
        return record


def assert_independent(candidate_model_id: str, judge_model_id: str, validators: tuple = ()) -> None:
    """A candidate's own model may only judge it alongside an independent validator."""
    if candidate_model_id != judge_model_id:
        return
    independent = [model for model in validators if model != candidate_model_id]
    if not independent:
        raise IndependenceViolation(
            f"Model {judge_model_id!r} produced this candidate and cannot be its only judge.",
            detail={"candidate_model_id": candidate_model_id, "judge_model_id": judge_model_id},
        )


def judge_candidate(
    baseline: ScoreCard,
    candidate: ScoreCard,
    *,
    candidate_model_id: str,
    judge_model_id: str,
    validators: tuple = (),
    reconciliation_summary: dict | None = None,
    minimum_delta: float = MINIMUM_MEANINGFUL_DELTA,
) -> JudgeDecision:
    assert_independent(candidate_model_id, judge_model_id, validators)
    comparison = compare(baseline, candidate)
    evidence: list[str] = [
        f"rubric={comparison['rubric_version']}",
        f"baseline_aggregate={comparison['baseline_aggregate']}",
        f"candidate_aggregate={comparison['candidate_aggregate']}",
        f"delta={comparison['delta']}",
    ]

    if candidate.blocking_failures:
        evidence.extend(candidate.blocking_failures)
        hallucinated = candidate.details.get("hallucinated_cells", [])[:5]
        evidence.extend(f"invented_value:{cell}" for cell in hallucinated)
        return JudgeDecision(
            candidate.candidate_id,
            "QUARANTINE",
            (
                "Candidate failed a blocking gate: it asserted confident values for cells the source "
                "does not support. The accepted baseline is preserved and this candidate is "
                "quarantined rather than merely rejected."
            ),
            tuple(evidence),
            tuple(candidate.blocking_failures),
            judge_model_id,
            comparison=comparison,
        )

    if comparison["blocking_regressions"]:
        evidence.extend(comparison["blocking_regressions"])
        return JudgeDecision(
            candidate.candidate_id,
            "REJECT",
            (
                "Candidate regressed on a blocking dimension. Aggregate improvement does not "
                "override a blocking regression; the baseline stands."
            ),
            tuple(evidence),
            tuple(comparison["blocking_regressions"]),
            judge_model_id,
            comparison=comparison,
        )

    if comparison["delta"] <= 0:
        evidence.extend(f"regression:{name}={delta}" for name, delta in sorted(comparison["regressions"].items()))
        return JudgeDecision(
            candidate.candidate_id,
            "REJECT",
            "Candidate did not score above the frozen baseline. The baseline is kept unchanged.",
            tuple(evidence),
            (),
            judge_model_id,
            comparison=comparison,
        )

    if comparison["delta"] < minimum_delta:
        return JudgeDecision(
            candidate.candidate_id,
            "REJECT",
            (
                f"Improvement of {comparison['delta']} is below the meaningful threshold "
                f"{minimum_delta}. Treated as noise; the baseline is kept."
            ),
            tuple(evidence),
            (),
            judge_model_id,
            comparison=comparison,
        )

    if reconciliation_summary:
        total = max(1, reconciliation_summary.get("total_rows", 0))
        share = reconciliation_summary.get("human_review_rows", 0) / total
        evidence.append(f"human_review_row_share={share:.3f}")
        if share > HUMAN_REVIEW_ROW_SHARE:
            return JudgeDecision(
                candidate.candidate_id,
                "HUMAN_REVIEW",
                (
                    "Candidate improves on the baseline, but most reconciliation rows still need a "
                    "human decision. Routing to review instead of auto-accepting."
                ),
                tuple(evidence),
                (),
                judge_model_id,
                comparison=comparison,
            )

    evidence.extend(f"improvement:{name}={delta}" for name, delta in sorted(comparison["improvements"].items()))
    return JudgeDecision(
        candidate.candidate_id,
        "ACCEPT",
        (
            f"Candidate improves the aggregate by {comparison['delta']} with no blocking failure "
            "and no blocking regression."
        ),
        tuple(evidence),
        (),
        judge_model_id,
        comparison=comparison,
    )
