from __future__ import annotations

from .models import HARD_VETOES, ImprovementProposal


def rank_proposals(proposals: list[ImprovementProposal]) -> list[ImprovementProposal]:
    """Deterministic NextBestMove ranker with hard vetoes.

    Higher value, lower risk, lower cost, higher confidence wins. Any hard
    veto leaves the proposal ranked but marked rejected.
    """
    scored: list[tuple[tuple, ImprovementProposal]] = []
    for proposal in proposals:
        vetoed = sorted(set(proposal.vetoes) & set(HARD_VETOES))
        status = "vetoed" if vetoed else proposal.status
        ranked = ImprovementProposal(
            proposal_id=proposal.proposal_id,
            title=proposal.title,
            evidence=list(proposal.evidence),
            value_score=proposal.value_score,
            risk_score=proposal.risk_score,
            cost_score=proposal.cost_score,
            reversibility=proposal.reversibility,
            confidence=proposal.confidence,
            autonomy_level=proposal.autonomy_level,
            vetoes=vetoed,
            status=status,
        )
        key = (
            0 if ranked.status == "vetoed" else 1,
            ranked.value_score,
            -ranked.risk_score,
            -ranked.cost_score,
            ranked.confidence,
            ranked.proposal_id,
        )
        scored.append((key, ranked))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored]
