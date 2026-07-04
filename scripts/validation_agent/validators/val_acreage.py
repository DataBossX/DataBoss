"""Acreage Footing Gate — tract gross acreage must reconcile to expected total."""
from __future__ import annotations

from decimal import Decimal
from typing import List

from .base_validator import BaseValidator, ValidationResult, PASS, FAIL, ESCALATE, SEV_HIGH, SEV_MED
from .wb_access import read_tract_blocks

TOL = Decimal("0.05")


class AcreageValidator(BaseValidator):
    gate_name = "Acreage Footing Gate"

    def run(self) -> List[ValidationResult]:
        expected = Decimal(str(self.config.get("expected_acreage", "637.42")))
        results: List[ValidationResult] = []
        if not self.workbook_path:
            return [self._result(ESCALATE, severity=SEV_MED, reason="No workbook path provided")]
        blocks = read_tract_blocks(self.workbook_path)
        if not blocks:
            return [self._result(ESCALATE, severity=SEV_HIGH,
                                 reason="No tract blocks located to foot acreage",
                                 recommended_action="Verify Title sheet structure / sheet classification")]
        total_gross = Decimal("0")
        for b in blocks:
            g = b["gross"] if b["gross"] is not None else Decimal("0")
            total_gross += g
            # per-tract footing: owner NMA sum vs gross
            diff = (b["owner_nma_sum"] - g)
            if b["gross"] is None:
                results.append(self._result(ESCALATE, severity=SEV_MED,
                    affected_subject=b["label"], reason="Tract gross acreage not found",
                    recommended_action="Confirm 'Containing: N acres' row"))
            elif diff > TOL:
                results.append(self._result(FAIL, severity=SEV_HIGH, repairable=False,
                    affected_subject=b["label"],
                    evidence={"gross": str(g), "owner_nma_sum": str(b["owner_nma_sum"])},
                    reason=f"Apparent OVER-conveyance: interests sum {b['owner_nma_sum']} exceed gross {g}",
                    recommended_action="Escalate — net reconciliation is a title judgment, not auto-repairable"))
            elif diff < -TOL and not b["has_balance"]:
                results.append(self._result(FAIL, severity=SEV_MED, repairable=False,
                    affected_subject=b["label"],
                    evidence={"gross": str(g), "owner_nma_sum": str(b["owner_nma_sum"])},
                    reason=f"Under-footed: interests sum {b['owner_nma_sum']} < gross {g} with no balance row",
                    recommended_action="Add 'Balance undetermined of record' row or locate owners (examiner)"))

        # Section-level reconciliation to the expected acreage.
        sec_diff = abs(total_gross - expected)
        if sec_diff <= TOL:
            results.append(self._result(PASS, severity=SEV_MED,
                evidence={"total_gross": str(total_gross), "expected": str(expected)},
                reason=f"Section gross {total_gross} reconciles to expected {expected}"))
        else:
            results.append(self._result(FAIL, severity=SEV_HIGH, repairable=False,
                evidence={"total_gross": str(total_gross), "expected": str(expected)},
                reason=f"Section gross {total_gross} != expected {expected} (diff {sec_diff})",
                recommended_action="Confirm government-lot acreage against official plat (examiner)"))
        return results
