"""Chain Continuity Gate.

For every current owner, a source-in (vesting) instrument must be present in the
record set. A missing vesting link is a legal fact and is ESCALATED — never
auto-repaired and never fabricated.
"""
from __future__ import annotations

from typing import Any, Dict, List

from validators.base_validator import Validator, make_result, PASS, ESCALATE, SEV_HIGH, SEV_MEDIUM


class ChainContinuityGate(Validator):
    gate_name = "Chain Continuity Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        tracts = context.get("tracts")
        if tracts is None:
            return [make_result(self.gate_name, ESCALATE, severity=SEV_MEDIUM,
                                reason="No normalized ownership data to check chain continuity.",
                                failure_class="Title Chain Gap", confidence=0.4)]
        results: List[Dict[str, Any]] = []
        for tract in tracts:
            for owner in tract.get("owners", []):
                if owner.get("source_in") in (None, "", "UNKNOWN"):
                    results.append(make_result(
                        self.gate_name, ESCALATE, severity=SEV_HIGH,
                        affected_subject=f"Tract {tract.get('tract')} / {owner.get('name','?')}",
                        evidence={"net_acres": str(owner.get("net_acres"))},
                        reason="No source-in / vesting instrument located for this owner.",
                        recommended_action=("Pull the prior deed / probate decree / heirship "
                                            "affidavit; do not credit as final."),
                        failure_class="Title Chain Gap", confidence=0.9))
        if not results:
            return [make_result(self.gate_name, PASS, severity=SEV_MEDIUM,
                                reason="Every current owner has a documented source-in.", confidence=1.0)]
        return results
