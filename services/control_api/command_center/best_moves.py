"""Best Moves Engine: deterministic first, model-assisted second.

Candidates may come from anywhere -- rules, project state, stale receipts,
blocked dependencies, watcher findings, a model, or Ryan. Ranking is a pure
function of declared factors and fixed weights, so the same state always
produces the same order and the score can be shown as arithmetic rather than
asserted.

The veto path is separate from the score path on purpose. A veto is not a large
negative weight that a high score could out-vote; it removes the move from the
eligible set entirely. No model score can override a hold, missing evidence, a
failed hash, a stale lease, a prohibited path, or a failed security gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from . import policy as policymod

#: Transparent, configurable ranking weights. They sum to 1.0 so a score is
#: directly readable as a 0-100 confidence-weighted benefit.
WEIGHTS: Mapping[str, float] = {
    "urgency": 0.18,
    "operational_benefit": 0.18,
    "blocker_relief": 0.15,
    "evidence_confidence": 0.12,
    "reversibility": 0.10,
    "dependency_readiness": 0.09,
    "state_freshness": 0.07,
    "low_effort": 0.06,
    "low_attention_cost": 0.05,
}

#: Risk is a penalty, not a factor, so a risky move cannot be lifted by volume.
RISK_PENALTY = 0.35


@dataclass
class MoveCandidate:
    """A proposed action plus the factors that justify it.

    All factor values are 0.0-1.0. ``release_risk`` is the only one where higher
    is worse.
    """

    move_id: str
    title: str
    operation: str
    resource_scope: str
    why_now: str
    expected_benefit: str
    risk: str
    verification_method: str
    failure_mode: str
    exact_next_click: str
    owner: str = "Ryan"
    origin: str = "rule"
    prerequisites: list = field(default_factory=list)
    evidence_used: list = field(default_factory=list)
    parameters: dict = field(default_factory=dict)

    urgency: float = 0.5
    operational_benefit: float = 0.5
    blocker_relief: float = 0.0
    evidence_confidence: float = 0.5
    reversibility: float = 1.0
    dependency_readiness: float = 1.0
    state_freshness: float = 1.0
    low_effort: float = 0.5
    low_attention_cost: float = 0.5
    release_risk: float = 0.0


@dataclass
class RankedMove:
    candidate: MoveCandidate
    score: float
    factor_contributions: dict
    eligible: bool
    vetoes: list
    risk_class: str
    requires_approval: bool
    requires_step_up: bool

    def to_dict(self) -> dict:
        c = self.candidate
        return {
            "move_id": c.move_id,
            "title": c.title,
            "exact_action": c.operation,
            "resource_scope": c.resource_scope,
            "why_now": c.why_now,
            "expected_benefit": c.expected_benefit,
            "risk": c.risk,
            "confidence": round(c.evidence_confidence, 3),
            "owner": c.owner,
            "origin": c.origin,
            "prerequisites": list(c.prerequisites),
            "evidence_used": list(c.evidence_used),
            "approval_required": self.requires_approval,
            "step_up_required": self.requires_step_up,
            "verification_method": c.verification_method,
            "if_it_fails": c.failure_mode,
            "exact_next_click": c.exact_next_click,
            "risk_class": self.risk_class,
            "score": round(self.score, 4),
            "score_breakdown": {k: round(v, 4) for k, v in self.factor_contributions.items()},
            "eligible": self.eligible,
            "vetoes": list(self.vetoes),
        }


def _score(candidate: MoveCandidate) -> tuple:
    contributions = {}
    for factor, weight in WEIGHTS.items():
        raw = float(getattr(candidate, factor, 0.0))
        raw = min(1.0, max(0.0, raw))
        contributions[factor] = raw * weight
    penalty = min(1.0, max(0.0, candidate.release_risk)) * RISK_PENALTY
    contributions["release_risk_penalty"] = -penalty
    total = sum(contributions.values())
    return max(0.0, total), contributions


def evaluate(
    candidates: Sequence[MoveCandidate],
    *,
    role: str,
    extra_holds: Sequence[str] = (),
    stale_lease_scopes: Sequence[str] = (),
    failed_hash_scopes: Sequence[str] = (),
    missing_evidence_moves: Sequence[str] = (),
    security_gate_failed: bool = False,
) -> list:
    """Rank candidates. Vetoes remove; they never merely subtract."""
    ranked: list = []
    for candidate in candidates:
        vetoes: list = []

        decision = policymod.classify(
            operation=candidate.operation,
            resource_scope=candidate.resource_scope,
            role=role,
            parameters=candidate.parameters,
            extra_holds=extra_holds,
        )
        if not decision.allowed:
            vetoes.extend(decision.reasons)

        # Hard vetoes that a score can never outrank.
        if policymod.scope_is_held(candidate.resource_scope, extra_holds) and \
                decision.risk_class != policymod.RISK_READ_ONLY:
            vetoes.append("Release hold applies to this scope.")
        if candidate.resource_scope in stale_lease_scopes:
            vetoes.append("Writer lease for this scope is stale.")
        if candidate.resource_scope in failed_hash_scopes:
            vetoes.append("An evidence hash check failed for this scope.")
        if candidate.move_id in missing_evidence_moves:
            vetoes.append("Required evidence is missing.")
        if security_gate_failed:
            vetoes.append("A security gate is failing; consequential moves are withheld.")
        if candidate.dependency_readiness <= 0.0:
            vetoes.append("A prerequisite is not ready.")

        score, contributions = _score(candidate)
        ranked.append(
            RankedMove(
                candidate=candidate,
                score=score,
                factor_contributions=contributions,
                eligible=not vetoes,
                vetoes=vetoes,
                risk_class=decision.risk_class,
                requires_approval=decision.requires_approval,
                requires_step_up=decision.requires_step_up,
            )
        )

    # Eligible first, then score, then a stable tiebreak on move_id so the
    # ordering is reproducible across runs.
    ranked.sort(key=lambda r: (not r.eligible, -r.score, r.candidate.move_id))
    return ranked


def best_next_move(ranked: Sequence[RankedMove]) -> Optional[RankedMove]:
    for move in ranked:
        if move.eligible:
            return move
    return None


def build_candidates(posture: Mapping) -> list:
    """Derive rule-based candidates from current system state.

    Purely deterministic: every candidate traces to an observable fact in the
    posture, never to a model opinion.
    """
    candidates: list = []

    candidates.append(
        MoveCandidate(
            move_id="mv_read_posture",
            title="Review current system posture",
            operation="status.read_posture",
            resource_scope="system.posture",
            why_now="Read-only orientation is always safe and refreshes every other decision.",
            expected_benefit="Confirms what is running, blocked, and waiting on you.",
            risk="None. Read-only, no state change.",
            verification_method="Posture response hash recorded in the audit ledger.",
            failure_mode="Nothing changes; the request is logged and retried.",
            exact_next_click="Tap 'Refresh posture' on the Command screen.",
            evidence_used=["control-kernel posture query"],
            urgency=0.35, operational_benefit=0.40, evidence_confidence=0.95,
            reversibility=1.0, low_effort=1.0, low_attention_cost=0.95, release_risk=0.0,
        )
    )

    blocked = list(posture.get("blocked") or [])
    if blocked:
        candidates.append(
            MoveCandidate(
                move_id="mv_triage_blocked",
                title=f"Triage {len(blocked)} blocked job(s)",
                operation="status.read_posture",
                resource_scope="system.posture",
                why_now=f"{len(blocked)} job(s) are FAILED, QUARANTINED, or awaiting rollback.",
                expected_benefit="Unblocks downstream work and clears the blocked queue.",
                risk="None to inspect. Any repair is a separate approved action.",
                verification_method="Each blocked job's last attempt and failure reason are shown.",
                failure_mode="Job stays blocked and remains visible on the Command screen.",
                exact_next_click="Open Jobs, filter Blocked.",
                evidence_used=[f"job:{j['job_id']}" for j in blocked[:5]],
                urgency=0.85, operational_benefit=0.75, blocker_relief=0.95,
                evidence_confidence=0.90, reversibility=1.0, low_effort=0.7,
                low_attention_cost=0.5, release_risk=0.0,
            )
        )

    needs = list(posture.get("needs_ryan") or [])
    if needs:
        candidates.append(
            MoveCandidate(
                move_id="mv_clear_approvals",
                title=f"Decide {len(needs)} pending approval(s)",
                operation="status.read_posture",
                resource_scope="system.posture",
                why_now="Work is stopped until you approve or reject it.",
                expected_benefit="Releases queued jobs that are otherwise idle.",
                risk="Each approval is single-use, scope-bound, and expires.",
                verification_method="Approval binding hash is checked again before execution.",
                failure_mode="Approval expires and the job returns to PENDING_APPROVAL.",
                exact_next_click="Open Decisions, review the top item.",
                evidence_used=[f"job:{j['job_id']}" for j in needs[:5]],
                urgency=0.95, operational_benefit=0.85, blocker_relief=0.90,
                evidence_confidence=0.95, reversibility=0.6, low_effort=0.8,
                low_attention_cost=0.3, release_risk=0.05,
            )
        )

    candidates.append(
        MoveCandidate(
            move_id="mv_verify_hashes",
            title="Verify synthetic artifact hashes",
            operation="artifact.verify_hashes",
            resource_scope="system.artifacts",
            why_now="Hash drift is cheap to detect now and expensive to discover later.",
            expected_benefit="Proves registered artifacts still match their recorded digests.",
            risk="None. Recompute and compare only.",
            verification_method="Recomputed SHA-256 compared against the registered value.",
            failure_mode="Mismatch quarantines the artifact and raises a DENY audit event.",
            exact_next_click="Tap 'Verify hashes' under More > Artifacts.",
            evidence_used=["artifact_versions table"],
            urgency=0.45, operational_benefit=0.55, evidence_confidence=0.90,
            reversibility=1.0, dependency_readiness=1.0, low_effort=0.85,
            low_attention_cost=0.9, release_risk=0.0,
        )
    )

    candidates.append(
        MoveCandidate(
            move_id="mv_sim_rollup",
            title="Simulate interest roll-up (synthetic project)",
            operation="title.simulate_interest_rollup",
            resource_scope="project.synthetic-alpha",
            why_now="Exercises exact-fraction title math without touching client evidence.",
            expected_benefit="Confirms the calculation path end to end before real data is ever used.",
            risk="SIMULATED only. No client data, no accepted artifact is touched.",
            verification_method="Result labelled SIMULATED in UI, API, audit, and receipt.",
            failure_mode="Job fails closed; an unbalanced chain is reported, never force-balanced.",
            exact_next_click="Tap 'Run simulation' on the Best Next Move card.",
            parameters={"project_id": "synthetic-alpha"},
            evidence_used=["synthetic fixture: tracts-alpha"],
            urgency=0.55, operational_benefit=0.70, evidence_confidence=0.80,
            reversibility=1.0, dependency_readiness=1.0, low_effort=0.75,
            low_attention_cost=0.8, release_risk=0.02,
        )
    )

    # Intentionally present and intentionally vetoed: proves a held scope stays
    # unreachable no matter how attractive the score looks.
    candidates.append(
        MoveCandidate(
            move_id="mv_section32_report",
            title="Build Section 32 client report",
            operation="report.simulate_draft_build",
            resource_scope="client.horizon.section32",
            why_now="Client work appears valuable, which is exactly why the hold must win.",
            expected_benefit="None available under the current hold.",
            risk="Prohibited. Section 32 is FOR REVIEW - HOLD - NO EXTERNAL RELEASE.",
            verification_method="Not applicable; the move is vetoed before scoring matters.",
            failure_mode="Fails closed with a DENY audit event.",
            exact_next_click="No action available. Hold must be cleared by a separate human lane.",
            parameters={"project_id": "section32"},
            evidence_used=[],
            urgency=1.0, operational_benefit=1.0, blocker_relief=1.0,
            evidence_confidence=1.0, reversibility=0.0, dependency_readiness=1.0,
            low_effort=1.0, low_attention_cost=1.0, release_risk=1.0,
        )
    )

    return candidates


def rank_for(posture: Mapping, *, role: str = "OWNER", **kwargs) -> list:
    return evaluate(build_candidates(posture), role=role, **kwargs)
