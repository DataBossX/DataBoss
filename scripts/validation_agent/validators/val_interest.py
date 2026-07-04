"""
Interest Conservation Gate.

Uses exact Fraction/Decimal arithmetic (never float equality) to test:
  * grantor_interest - conveyed + retained == 0  (conservation), and
  * per-tract over/under-conveyance of net mineral acres.
Over-conveyance and unresolved balances are FAIL/ESCALATE, never auto-repaired.
"""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import List, Optional

from .base_validator import BaseValidator, ValidationResult, PASS, FAIL, ESCALATE, SEV_HIGH, SEV_MED
from .wb_access import read_tract_blocks

TOL = Decimal("0.05")


def conservation_residual(grantor, conveyed, retained) -> Fraction:
    """Return grantor - conveyed + retained as an exact Fraction (should be 0)."""
    g = Fraction(str(grantor))
    c = Fraction(str(conveyed))
    r = Fraction(str(retained))
    return g - c + r


class InterestValidator(BaseValidator):
    gate_name = "Interest Conservation Gate"

    def run(self) -> List[ValidationResult]:
        results: List[ValidationResult] = []

        # 1) Optional explicit conservation triples passed via config (chain evidence).
        for triple in self.config.get("conservation_checks", []):
            resid = conservation_residual(triple["grantor"], triple["conveyed"], triple["retained"])
            if resid == 0:
                results.append(self._result(PASS, severity=SEV_MED,
                    affected_subject=triple.get("subject", "conservation"),
                    reason="grantor - conveyed + retained = 0 (exact)"))
            else:
                results.append(self._result(FAIL, severity=SEV_HIGH, repairable=False,
                    affected_subject=triple.get("subject", "conservation"),
                    evidence={"residual": str(resid)},
                    reason=f"Interest not conserved; residual {resid} != 0",
                    recommended_action="Escalate — conveyance math gap is a title issue"))

        # 2) Per-tract NMA conservation vs gross.
        if self.workbook_path:
            for b in read_tract_blocks(self.workbook_path):
                if b["gross"] is None:
                    continue
                g = b["gross"]
                s = b["owner_nma_sum"]
                diff = s - g
                if diff > TOL:
                    results.append(self._result(FAIL, severity=SEV_HIGH, repairable=False,
                        affected_subject=b["label"],
                        evidence={"gross": str(g), "sum": str(s), "over": str(diff)},
                        reason=f"Over-conveyance of {diff} NMA (sum {s} > gross {g})",
                        recommended_action="Escalate for net reconciliation (examiner)"))
                elif diff < -TOL and not b["has_balance"]:
                    results.append(self._result(ESCALATE, severity=SEV_MED, repairable=False,
                        affected_subject=b["label"],
                        evidence={"gross": str(g), "sum": str(s), "under": str(diff)},
                        reason=f"Under-conveyance of {abs(diff)} NMA with no balance row",
                        recommended_action="Add disclosed balance row or locate owners (examiner)"))
                else:
                    results.append(self._result(PASS, severity=SEV_MED,
                        affected_subject=b["label"],
                        evidence={"gross": str(g), "sum": str(s)},
                        reason="Tract interests conserve within tolerance"))

        if not results:
            results.append(self._result(ESCALATE, severity=SEV_MED,
                reason="No interest data available to validate"))
        return results
