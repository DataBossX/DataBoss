"""Deterministic acreage verification -- the Python authority on the math.

The LLM agents may *reason* about how a title chains, but they are never
trusted to do arithmetic. Every tract result is checked here with
:class:`decimal.Decimal` under a fixed context. A tract passes only when:

1. The sum of final owners' net acres equals the tract acreage within an exact
   tolerance of ``0.000001`` (rule 13).
2. No owner holds negative acreage or negative working interest (rule 12).
3. No owner in the chain conveyed more than they owned (rule 11).

The verifier is pure and side-effect free: given the same owners and tract
acreage it always returns the same :class:`~schemas.VerificationResult`, which
is what makes the self-healing loop deterministic and reproducible.
"""

from __future__ import annotations

from decimal import Decimal, getcontext
from typing import Iterable, List, Optional, Sequence

from schemas import (
    ACRE_QUANT,
    TOLERANCE,
    Conveyance,
    OwnerInterest,
    VerificationResult,
    quantize_acres,
)

# A generous precision so intermediate sums never lose the sixth decimal.
getcontext().prec = 34


def sum_acres(owners: Iterable[OwnerInterest]) -> Decimal:
    """Total the net acres of a set of owners, quantized to 0.000001."""
    total = sum((o.acres for o in owners), Decimal("0"))
    return total.quantize(ACRE_QUANT)


def find_negative_holdings(owners: Sequence[OwnerInterest]) -> List[str]:
    """Return human-readable errors for any negative acreage/WI (rule 12)."""
    errors: List[str] = []
    for o in owners:
        if o.acres < 0:
            errors.append(f"NEGATIVE ACRES: {o.owner!r} holds {o.acres} ac (< 0).")
        if o.wi < 0:
            errors.append(f"NEGATIVE WI: {o.owner!r} holds working interest {o.wi} (< 0).")
    return errors


def find_over_conveyances(
    conveyances: Sequence[Conveyance],
    tract_acres: Decimal,
) -> List[str]:
    """Replay a tract's conveyances and report any over-conveyance (rule 11).

    Walks the ordered conveyances maintaining a running holding per grantor.
    An owner starts with 0 known acres; the first time they appear as a grantee
    their balance grows, and a conveyance out that exceeds the balance is an
    over-conveyance. The tract's original (root) owner is seeded with the full
    tract acreage so the first conveyance out is measured against reality.
    """
    if not conveyances:
        return []

    holdings: dict[str, Decimal] = {}
    errors: List[str] = []

    # Seed the earliest grantor with the full tract so the root conveyance is
    # measured against the true opening balance rather than zero.
    root = conveyances[0].grantor.strip()
    if root:
        holdings[root] = quantize_acres(tract_acres)

    for c in conveyances:
        moved = c.acres if c.acres is not None else None
        if moved is None:
            # A fractional or lease-only (OGL/ASSN) conveyance moves no net
            # mineral acres; it cannot over-convey acreage.
            continue
        grantor = c.grantor.strip()
        grantee = c.grantee.strip()
        have = holdings.get(grantor, Decimal("0"))
        if moved - have > TOLERANCE:
            errors.append(
                f"OVER-CONVEYANCE: {grantor!r} conveyed {moved} ac to "
                f"{grantee!r} but held only {have} ac "
                f"(instrument {c.instrument_no or c.bk_pg or '?'})."
            )
        holdings[grantor] = have - moved
        if grantee:
            holdings[grantee] = holdings.get(grantee, Decimal("0")) + moved

    return errors


def verify_tract(
    owners: Sequence[OwnerInterest],
    tract_acres,
    tract: str = "",
    conveyances: Optional[Sequence[Conveyance]] = None,
) -> VerificationResult:
    """Verify a single tract and return a :class:`VerificationResult`.

    ``owners`` are the *final* owners produced by chaining; ``tract_acres`` is
    the controlling gross acreage for the tract; ``conveyances`` (optional) is
    the ordered chain used to detect over-conveyance.
    """
    expected = quantize_acres(tract_acres)
    total = sum_acres(owners)
    delta = (total - expected).quantize(ACRE_QUANT)

    errors: List[str] = []
    errors.extend(find_negative_holdings(owners))
    if conveyances:
        errors.extend(find_over_conveyances(conveyances, expected))

    within_tolerance = abs(delta) <= TOLERANCE
    if not within_tolerance:
        direction = "over" if delta > 0 else "under"
        errors.append(
            f"UNBALANCED: final owners total {total} ac vs tract {expected} ac "
            f"({direction} by {abs(delta)} ac)."
        )

    passed = within_tolerance and not errors

    suggestion = ""
    if not passed:
        suggestion = _build_correction_suggestion(owners, expected, delta, errors)

    return VerificationResult(
        tract=tract,
        expected_acres=expected,
        calculated_total=total,
        delta=delta,
        passed=passed,
        errors=errors,
        correction_suggestion=suggestion,
    )


def _build_correction_suggestion(
    owners: Sequence[OwnerInterest],
    expected: Decimal,
    delta: Decimal,
    errors: Sequence[str],
) -> str:
    """Craft precise, machine-readable feedback for the auditor agent.

    We never tell the agent to blindly "fix the last owner" -- instead we hand
    it the exact delta, the owner table, and the concrete rule violations so it
    can re-reason the chain. If the only problem is a small residual delta we
    additionally name it as a candidate rounding/assumption gap.
    """
    lines = [
        f"Tract must total exactly {expected} net acres.",
        f"Current final-owner total is off by {delta} ac.",
    ]
    if any("OVER-CONVEYANCE" in e for e in errors):
        lines.append(
            "An owner conveyed more than they held; re-check the deducting "
            "conveyance -- no owner may convey more than they own (rule 11)."
        )
    if any("NEGATIVE" in e for e in errors):
        lines.append(
            "A holding went negative; re-order or correct the deductions "
            "(no negative ownership, rule 12)."
        )
    if abs(delta) > 0 and not any(("OVER-CONVEYANCE" in e or "NEGATIVE" in e) for e in errors):
        lines.append(
            "If the runsheet legals/notes cannot close this gap, allocate the "
            f"residual {delta} ac as a NOTED ASSUMPTION and flag it for review "
            "(rule 14) -- do not silently force-balance (rule 6)."
        )
    lines.append("Owner table:")
    for o in owners:
        ogl = f" OGL={o.ogl}" if o.ogl else ""
        lines.append(f"  - {o.owner}: {o.acres} ac{ogl}")
    return "\n".join(lines)
