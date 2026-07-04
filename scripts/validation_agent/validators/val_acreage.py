"""Acreage Footing Gate.

Tract gross acres must sum to the configured expected total (default 637.42)
using Decimal arithmetic. Per-tract owner net acres must foot to that tract's
gross (within a tiny Decimal tolerance for documented rounding). A wrong total
is a computational FAIL; an unallocated remainder is disclosed as ESCALATE
(open balance), never invented.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

from validators.base_validator import (Validator, make_result, PASS, FAIL, ESCALATE,
                                       SEV_HIGH, SEV_MEDIUM)

TOLERANCE = Decimal("0.01")


def _dec(v: Any) -> Decimal:
    if v in (None, "", "TBD"):
        return Decimal(0)
    return Decimal(str(v))


class AcreageFootingGate(Validator):
    gate_name = "Acreage Footing Gate"

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        tracts = context.get("tracts")
        expected = _dec(context.get("expected_acres", "637.42"))
        if tracts is None:
            return [make_result(self.gate_name, ESCALATE, severity=SEV_MEDIUM,
                                reason="No normalized tract data to foot acreage.",
                                recommended_action="Provide extracted tract gross/net acres.",
                                failure_class="Computational Mismatch", confidence=0.4)]
        results: List[Dict[str, Any]] = []
        gross_total = Decimal(0)
        for tract in tracts:
            gross = _dec(tract.get("gross_acres"))
            gross_total += gross
            owners_sum = sum((_dec(o.get("net_acres")) for o in tract.get("owners", [])), Decimal(0))
            open_balance = _dec(tract.get("open_balance"))
            footed = owners_sum + open_balance
            if abs(footed - gross) > TOLERANCE:
                results.append(make_result(
                    self.gate_name, FAIL, severity=SEV_HIGH,
                    affected_subject=f"Tract {tract.get('tract')}",
                    evidence={"gross": str(gross), "owners_sum": str(owners_sum),
                              "open_balance": str(open_balance), "footed": str(footed)},
                    reason=f"Tract owners+open_balance ({footed}) != gross ({gross}).",
                    recommended_action="Recheck tract grid SUMIF/allocation.",
                    failure_class="Computational Mismatch", confidence=0.9))
            elif open_balance > TOLERANCE:
                results.append(make_result(
                    self.gate_name, ESCALATE, severity=SEV_MEDIUM,
                    affected_subject=f"Tract {tract.get('tract')}",
                    evidence={"open_balance": str(open_balance), "gross": str(gross)},
                    reason=f"Tract {tract.get('tract')} carries an open balance of {open_balance} NMA.",
                    recommended_action="Obtain vesting instruments; do not invent owners.",
                    failure_class="Missing Source", confidence=0.85))

        if abs(gross_total - expected) > TOLERANCE:
            results.append(make_result(
                self.gate_name, FAIL, severity=SEV_HIGH,
                affected_subject="Section total",
                evidence={"gross_total": str(gross_total), "expected": str(expected)},
                reason=f"Sum of tract gross acres {gross_total} != expected {expected}.",
                recommended_action="Verify tract legals/acreage against plat/GLO.",
                failure_class="Computational Mismatch", confidence=0.95))
        else:
            results.append(make_result(
                self.gate_name, PASS, severity=SEV_MEDIUM,
                affected_subject="Section total",
                evidence={"gross_total": str(gross_total), "expected": str(expected)},
                reason=f"Section gross acres foot to {gross_total} (expected {expected}).",
                confidence=1.0))
        return results
