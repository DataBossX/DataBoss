"""Oklahoma Division-of-Interest (DOI) royalty math.

The DOI decimal is the fraction of unit production a mineral owner is paid on:

    decimal_interest = (net_mineral_acres / spacing_unit_acres) * royalty_rate

In Oklahoma, statutory spacing units are commonly 640 ac (1 section) for gas
and 40/80/160 ac for oil; royalty_rate is the lease fraction (e.g. 3/16 = 0.1875).
All arithmetic uses Decimal — paying mineral owners on a binary float is how you
end up in front of the Oklahoma Corporation Commission.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from evoswarm.schemas import Money, RoyaltyInput, RoyaltyResult

EIGHT_PLACES = Decimal("0.00000001")
CENTS = Decimal("0.01")


def division_order_decimal(net_mineral_acres: Decimal, spacing_unit_acres: Decimal,
                           royalty_rate: Decimal) -> Decimal:
    """Return the DOI decimal, rounded to 8 places per industry convention."""
    if spacing_unit_acres <= 0:
        raise ValueError("spacing_unit_acres must be > 0")
    raw = (net_mineral_acres / spacing_unit_acres) * royalty_rate
    return raw.quantize(EIGHT_PLACES, rounding=ROUND_HALF_UP)


def compute_royalty(inp: RoyaltyInput) -> RoyaltyResult:
    """Compute monthly gross/net royalty for a single owner's interest."""
    decimal_interest = division_order_decimal(
        inp.net_mineral_acres, inp.spacing_unit_acres, inp.royalty_rate
    )
    gross = (inp.monthly_production_bbl * inp.price_per_bbl.amount).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )
    net = (gross * decimal_interest).quantize(CENTS, rounding=ROUND_HALF_UP)
    explanation = (
        f"DOI = ({inp.net_mineral_acres} NMA / {inp.spacing_unit_acres} ac unit) "
        f"x {inp.royalty_rate} royalty = {decimal_interest}. "
        f"Net = {inp.monthly_production_bbl} bbl x ${inp.price_per_bbl.amount}/bbl "
        f"x {decimal_interest} = ${net}."
    )
    return RoyaltyResult(
        decimal_interest=decimal_interest,
        gross_monthly=Money(amount=gross),
        net_monthly=Money(amount=net),
        explanation=explanation,
    )
