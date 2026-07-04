"""Interest Conservation Gate.

Uses :class:`fractions.Fraction` for exact arithmetic — never float ``==``.
For each grantor entry the identity ``interest_in - conveyed - retained == 0``
must hold exactly. Over/under-conveyance is detected and reported. Because a
conservation break can stem from a missing source-in (a legal fact), the gate
routes unresolved breaks to escalation rather than marking them auto-repairable.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any, Dict, List

from validators.base_validator import (Validator, make_result, PASS, FAIL, ESCALATE,
                                       SEV_HIGH, SEV_MEDIUM)


def _frac(v: Any) -> Fraction:
    if v is None or v == "":
        return Fraction(0)
    if isinstance(v, Fraction):
        return v
    if isinstance(v, str) and "/" in v:
        num, den = v.split("/", 1)
        return Fraction(int(num.strip()), int(den.strip()))
    return Fraction(str(v))


class InterestConservationGate(Validator):
    gate_name = "Interest Conservation Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        tracts = context.get("tracts")
        if tracts is None:
            return [make_result(self.gate_name, ESCALATE, severity=SEV_MEDIUM,
                                reason="No normalized tract/interest data available to check.",
                                recommended_action="Provide extracted interest ledger or mark for manual review.",
                                failure_class="Computational Mismatch", confidence=0.4)]
        results: List[Dict[str, Any]] = []
        for tract in tracts:
            for entry in tract.get("conveyances", []):
                interest_in = _frac(entry.get("interest_in"))
                conveyed = _frac(entry.get("conveyed"))
                retained = _frac(entry.get("retained"))
                delta = interest_in - conveyed - retained
                subject = f"Tract {tract.get('tract')} / {entry.get('grantor','?')}"
                if delta == 0:
                    continue
                over = delta < 0
                kind = "OVERCONVEYANCE" if over else "UNDERCONVEYANCE"
                # A grantor conveying more than they own usually means a missing
                # source-in (legal fact) -> escalate, not auto-repair.
                results.append(make_result(
                    self.gate_name, FAIL if not over else ESCALATE,
                    severity=SEV_HIGH,
                    affected_sheet=entry.get("sheet"),
                    affected_cell_or_range=entry.get("cell"),
                    affected_subject=subject,
                    evidence={"interest_in": str(interest_in), "conveyed": str(conveyed),
                              "retained": str(retained), "delta": str(delta), "kind": kind},
                    reason=f"{kind}: interest_in - conveyed - retained = {delta} (must be 0).",
                    recommended_action=("Locate the grantor's source-in / vesting instrument; "
                                        "do not auto-balance."),
                    failure_class="Title Chain Gap" if over else "Computational Mismatch",
                    confidence=0.95))
        if not results:
            return [make_result(self.gate_name, PASS, severity=SEV_MEDIUM,
                                reason="All grantor conveyances conserve exactly (Fraction math).",
                                confidence=1.0)]
        return results
