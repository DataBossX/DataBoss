"""Acreage Footing Gate.

Tract acreage must foot to exactly the expected total (default 637.42 acres)
using Decimal arithmetic. Float comparison is never used.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Iterable

from .base_validator import BaseValidator, ValidationResult, SEVERITY_HIGH


def _to_decimal(v) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Non-numeric acreage value: {v!r}")


def sum_acreage(values: Iterable) -> Decimal:
    total = Decimal("0")
    for v in values:
        total += _to_decimal(v)
    return total


def check_acreage(values: Iterable, expected: Decimal) -> dict:
    """Return a plain-dict result for the acreage footing check."""
    total = sum_acreage(values)
    expected = Decimal(str(expected))
    diff = (total - expected).quantize(Decimal("0.01"))
    return {
        "total": str(total),
        "expected": str(expected),
        "difference": str(diff),
        "reconciles": diff == Decimal("0.00"),
    }


class AcreageFootingValidator(BaseValidator):
    gate_name = "Acreage Footing Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        acreages = context.get("tract_acreages")
        expected = Decimal(str(context.get("expected_acreage", "637.42")))
        if not acreages:
            return [self._escalate(
                severity=SEVERITY_HIGH,
                affected_subject="tract acreage",
                reason="No tract acreage values were extractable from the workbook.",
                recommended_action="Examiner must confirm the tracts sheet and "
                                    "acreage column.",
                confidence=0.9,
            )]
        try:
            res = check_acreage(acreages, expected)
        except ValueError as e:
            return [self._error(
                severity=SEVERITY_HIGH, affected_subject="tract acreage",
                reason=str(e), recommended_action="Fix non-numeric acreage cell.",
            )]
        if res["reconciles"]:
            return [self._pass(
                affected_subject="tract acreage",
                evidence=res,
                reason=f"Acreage foots to {res['total']} == expected {res['expected']}.",
            )]
        return [self._fail(
            severity=SEVERITY_HIGH,
            repairable=False,  # acreage mismatch is a factual discrepancy
            affected_subject="tract acreage",
            evidence=res,
            reason=f"Acreage total {res['total']} != expected {res['expected']} "
                   f"(diff {res['difference']}).",
            recommended_action="Examiner review: reconcile tract acreage against "
                               "legal descriptions; do not auto-adjust.",
            confidence=0.95,
        )]
