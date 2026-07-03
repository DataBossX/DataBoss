"""Chain Continuity Gate and Reservation Carry-Forward checks.

Verifies that each conveyance's grantor is vested — i.e. appears as a grantee
(or root sovereign/patent) earlier in the chain. A grantor who is not vested,
a missing probate link, or an ambiguous reservation is ESCALATED and never
auto-repaired.
"""

from __future__ import annotations

from typing import Any

from .base_validator import BaseValidator, ValidationResult, SEVERITY_HIGH


def analyze_chain(links: list[dict]) -> dict:
    """Walk an ordered chain of {grantor, grantee, vested_root?} links.

    Returns a report of gaps where a grantor was never vested.
    """
    vested: set[str] = set()
    gaps: list[dict] = []
    for i, link in enumerate(links):
        grantor = str(link.get("grantor", "")).strip().lower()
        grantee = str(link.get("grantee", "")).strip().lower()
        is_root = bool(link.get("vested_root"))
        if not grantor:
            gaps.append({"index": i, "issue": "missing_grantor", "link": link})
        elif not is_root and grantor not in vested:
            gaps.append({"index": i, "issue": "grantor_not_vested",
                         "grantor": link.get("grantor"), "link": link})
        if grantee:
            vested.add(grantee)
    return {"links": len(links), "gaps": gaps, "continuous": not gaps}


class ChainContinuityValidator(BaseValidator):
    gate_name = "Chain Continuity Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        links = context.get("chain_links")
        if not links:
            return [self._escalate(
                severity=SEVERITY_HIGH, affected_subject="title chain",
                reason="No chain-of-title links extractable; vesting cannot be "
                       "verified.",
                recommended_action="Examiner must supply/confirm the runsheet.",
                confidence=0.9,
            )]
        report = analyze_chain(links)
        if report["continuous"]:
            return [self._pass(
                affected_subject="title chain", evidence=report,
                reason="Chain of title is continuous; every grantor is vested.",
            )]
        return [self._escalate(
            severity=SEVERITY_HIGH, repairable=False,
            affected_subject="title chain", evidence=report,
            reason=f"{len(report['gaps'])} chain gap(s): grantor not vested / "
                   f"missing link. Title facts cannot be inferred.",
            recommended_action="Human examiner must resolve vesting, probate, or "
                               "reservation carry-forward. Never auto-repaired.",
            confidence=0.95,
        )]
