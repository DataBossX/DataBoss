"""Interest Conservation Gate.

Interest math uses Decimal / Fraction exclusively — never unsafe float
comparison. For every conveyance:

    grantor_interest - conveyed + retained == 0   (conservation)

Overconveyance (conveyed + retained > grantor_interest) and underconveyance
(conveyed + retained < grantor_interest) are both detected.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from .base_validator import BaseValidator, ValidationResult, SEVERITY_HIGH


def _to_fraction(v: Any) -> Fraction:
    """Parse a decimal/fraction/percent-ish value into an exact Fraction."""
    if isinstance(v, Fraction):
        return v
    if isinstance(v, int):
        return Fraction(v, 1)
    s = str(v).strip().replace("%", "")
    if "/" in s:
        num, _, den = s.partition("/")
        return Fraction(int(num.strip()), int(den.strip()))
    # Decimal string -> exact Fraction (no float rounding).
    if "." in s:
        whole, _, frac = s.partition(".")
        whole = whole or "0"
        sign = -1 if whole.startswith("-") else 1
        whole_i = abs(int(whole))
        digits = len(frac)
        numerator = whole_i * (10 ** digits) + int(frac or "0")
        return Fraction(sign * numerator, 10 ** digits)
    return Fraction(int(s), 1)


def check_conservation(grantor_interest: Any, conveyed: Any,
                       retained: Any) -> dict:
    """Exact conservation check. Returns a plain dict."""
    g = _to_fraction(grantor_interest)
    c = _to_fraction(conveyed)
    r = _to_fraction(retained)
    residual = g - c + r  # should be 0 for conservation: g == c - r? see note
    # Conservation law: what the grantor had must equal what was conveyed plus
    # what was retained: g == c + r  ->  residual2 = g - (c + r)
    balance = g - (c + r)
    status = "balanced"
    if balance < 0:
        status = "overconveyance"
    elif balance > 0:
        status = "underconveyance"
    return {
        "grantor_interest": str(g),
        "conveyed": str(c),
        "retained": str(r),
        "balance": str(balance),
        "balance_float": float(balance),
        "status": status,
        "balanced": balance == 0,
    }


class InterestConservationValidator(BaseValidator):
    gate_name = "Interest Conservation Gate"

    def run(self, context: dict) -> list[ValidationResult]:
        rows = context.get("interest_rows") or []
        if not rows:
            return [self._escalate(
                severity=SEVERITY_HIGH, affected_subject="interest conservation",
                reason="No interest conveyance rows extractable from the workbook.",
                recommended_action="Examiner must confirm the conveyance ledger.",
                confidence=0.9,
            )]
        results: list[ValidationResult] = []
        for row in rows:
            subject = row.get("subject", "conveyance")
            try:
                res = check_conservation(
                    row["grantor_interest"], row["conveyed"], row["retained"]
                )
            except (KeyError, ValueError, ZeroDivisionError) as e:
                results.append(self._error(
                    severity=SEVERITY_HIGH, affected_subject=subject,
                    reason=f"Interest parse error: {e}",
                    recommended_action="Examiner review of interest cell format.",
                ))
                continue
            if res["balanced"]:
                results.append(self._pass(
                    affected_subject=subject, evidence=res,
                    reason=f"Interest conserved for {subject} (balance 0).",
                ))
            else:
                results.append(self._fail(
                    severity=SEVERITY_HIGH, repairable=False,
                    affected_subject=subject, evidence=res,
                    reason=f"{res['status']} for {subject}: "
                           f"grantor {res['grantor_interest']} != conveyed "
                           f"{res['conveyed']} + retained {res['retained']} "
                           f"(balance {res['balance']}).",
                    recommended_action="Title examiner must reconcile the "
                                       "conveyance; interest facts are never "
                                       "auto-repaired.",
                    confidence=0.97,
                ))
        return results
