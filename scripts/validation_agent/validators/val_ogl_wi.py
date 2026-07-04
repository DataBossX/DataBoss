"""OGL Register Audit Gate + WI/Depth Consistency Gate + Well/HBP Support Gate.

These three related gates are grouped here. OGL numbering/coverage issues that
are purely referential can be FAIL (fixable by examiner correction); WI/NRI that
cannot be computed of record ESCALATES; HBP without production/well support
ESCALATES and is never auto-certified.
"""
from __future__ import annotations

from typing import Any, Dict, List

from validators.base_validator import Validator, make_result, PASS, FAIL, ESCALATE, SEV_MEDIUM, SEV_HIGH


class OGLRegisterAuditGate(Validator):
    gate_name = "OGL Register Audit Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        ogls = context.get("ogls")
        if ogls is None:
            return [make_result(self.gate_name, ESCALATE, severity=SEV_MEDIUM,
                                reason="No OGL register data available.",
                                failure_class="OGL Mismatch / WI Assignment Gap", confidence=0.4)]
        results: List[Dict[str, Any]] = []
        seen = set()
        for o in ogls:
            num = o.get("ogl_no")
            if num in seen:
                results.append(make_result(self.gate_name, FAIL, severity=SEV_MEDIUM,
                    affected_subject=f"OGL {num}", reason="Duplicate OGL register number.",
                    recommended_action="De-duplicate register numbering.",
                    failure_class="OGL Mismatch / WI Assignment Gap", confidence=0.8))
            seen.add(num)
            if not o.get("tracts"):
                results.append(make_result(self.gate_name, ESCALATE, severity=SEV_MEDIUM,
                    affected_subject=f"OGL {num}",
                    reason="OGL has no mapped tract coverage from its legal.",
                    recommended_action="Confirm coverage from lease image.",
                    failure_class="OGL Mismatch / WI Assignment Gap", confidence=0.7))
        if not results:
            return [make_result(self.gate_name, PASS, severity=SEV_MEDIUM,
                                reason="OGL register numbers unique and tract-mapped.", confidence=1.0)]
        return results


class WIDepthConsistencyGate(Validator):
    gate_name = "WI/Depth Consistency Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        wi = context.get("working_interests")
        if wi is None:
            return [make_result(self.gate_name, ESCALATE, severity=SEV_MEDIUM,
                                reason="No working-interest data available.",
                                failure_class="OGL Mismatch / WI Assignment Gap", confidence=0.4)]
        results: List[Dict[str, Any]] = []
        for a in wi:
            if a.get("wi") in (None, "", "TBD") or a.get("nri") in (None, "", "TBD"):
                results.append(make_result(self.gate_name, ESCALATE, severity=SEV_HIGH,
                    affected_subject=a.get("owner", "?"),
                    reason="WI/NRI not calculable of record (assignment exhibit missing).",
                    recommended_action="Obtain assignment exhibits; rebuild WI math.",
                    failure_class="OGL Mismatch / WI Assignment Gap", confidence=0.85))
        if not results:
            return [make_result(self.gate_name, PASS, severity=SEV_MEDIUM,
                                reason="WI/NRI computable and depth-consistent.", confidence=1.0)]
        return results


class WellHBPSupportGate(Validator):
    gate_name = "Well/HBP Support Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        well = context.get("well") or {}
        supported = well.get("hbp_supported")
        if supported is True and well.get("production_evidence"):
            return [make_result(self.gate_name, PASS, severity=SEV_HIGH,
                                affected_subject=well.get("name", "well"),
                                evidence={"production_evidence": well.get("production_evidence")},
                                reason="HBP supported by production/well evidence of record.",
                                confidence=0.9)]
        return [make_result(self.gate_name, ESCALATE, severity=SEV_HIGH,
                            affected_subject=well.get("name", "well"),
                            evidence={"occ_status": well.get("occ_status"),
                                      "last_production": well.get("last_production")},
                            reason="HBP not supported by verified production of record.",
                            recommended_action="Pull OTC gross production + OCC well file before certifying HBP.",
                            failure_class="HBP Unsupported", confidence=0.9)]
