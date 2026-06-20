"""EvoLoop — eval-gated, human-approved self-improvement (Branch 3).

HONEST SCOPE: this is *not* unsupervised self-modifying production code. The loop
(1) runs the agent fleet against a frozen eval set, (2) lets an "evolver" agent
propose a prompt/spec diff, (3) re-scores the candidate, and (4) if it beats the
incumbent by the configured margin AND `require_human_pr` is set, it opens a PR
for a human to merge. Nothing rewrites the running swarm without that gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from evoswarm.settings import settings


@dataclass(frozen=True)
class EvalReport:
    candidate_id: str
    score: float
    baseline_score: float
    passed_cases: int
    total_cases: int

    @property
    def improved(self) -> bool:
        return self.score - self.baseline_score >= 0.0

    @property
    def promotable(self) -> bool:
        return (
            settings.evoloop_enabled
            and self.score >= settings.evoloop_min_eval_score
            and self.improved
        )


def decide(report: EvalReport) -> str:
    """Return the action the orchestrator should take for a candidate."""
    if not report.promotable:
        return "reject"
    if settings.evoloop_require_human_pr:
        return "open_pr"  # human merges; never auto-deploy
    return "auto_promote"  # only reachable if an operator explicitly opts out
