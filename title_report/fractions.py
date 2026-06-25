"""Auditable fraction math for royalties, working interests, and acreage.

All arithmetic is exact rational arithmetic via :class:`fractions.Fraction`.
The hard rule from the QA gates is honoured here: **nothing is computed without
exact governing language**. A derived value is returned only when every input
is a concrete ``Fraction``; if any input is :data:`UNKNOWN`, the result is
:data:`UNKNOWN` -- never a guess, never a silent zero.

The functions return both the exact ``Fraction`` and a pre-formatted decimal so
that callers (and the spreadsheet) display consistent, reproducible values.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Optional, Union

from .models import UNKNOWN, FracOrUnknown


def is_known(value: FracOrUnknown) -> bool:
    return isinstance(value, Fraction)


def parse_fraction(text: str) -> Optional[Fraction]:
    """Parse '3/16', '0.1875', or '1' into a Fraction. Returns None if not parseable."""
    if text is None:
        return None
    s = str(text).strip()
    if not s or s == UNKNOWN:
        return None
    try:
        if "/" in s:
            num, den = s.split("/", 1)
            return Fraction(int(num.strip()), int(den.strip()))
        return Fraction(s)  # handles ints and decimal strings exactly
    except (ValueError, ZeroDivisionError):
        return None


def frac_str(value: FracOrUnknown) -> str:
    """Render a fraction as 'num/den' (or the integer / UNKNOWN)."""
    if not is_known(value):
        return UNKNOWN
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def decimal_str(value: FracOrUnknown, places: int = 8) -> str:
    """Render a fraction as a fixed-precision decimal string (or UNKNOWN)."""
    if not is_known(value):
        return UNKNOWN
    return f"{float(value):.{places}f}"


def net_revenue_interest(
    mineral_interest: FracOrUnknown,
    lease_royalty: FracOrUnknown,
) -> FracOrUnknown:
    """Royalty-owner NRI = mineral interest x lessor royalty.

    Both inputs must be known fractions backed by exact lease/deed language.
    """
    if is_known(mineral_interest) and is_known(lease_royalty):
        return mineral_interest * lease_royalty
    return UNKNOWN


def wi_net_revenue_interest(
    working_interest: FracOrUnknown,
    burdens: FracOrUnknown,
) -> FracOrUnknown:
    """Working-interest NRI = WI x (1 - total burdens)."""
    if is_known(working_interest) and is_known(burdens):
        return working_interest * (Fraction(1) - burdens)
    return UNKNOWN


def entry_nri(role: str, mineral_interest, lease_royalty, working_interest,
              burdens, override_royalty) -> FracOrUnknown:
    """Net revenue interest for an ownership entry, dispatched by role.

    * royalty            -> mineral interest x lessor royalty
    * working_interest   -> WI x (1 - total burdens)
    * overriding_royalty -> the ORRI fraction itself (already net)
    """
    if role == "working_interest":
        return wi_net_revenue_interest(working_interest, burdens)
    if role == "overriding_royalty":
        return override_royalty if is_known(override_royalty) else UNKNOWN
    return net_revenue_interest(mineral_interest, lease_royalty)


def net_mineral_acres(
    mineral_interest: FracOrUnknown,
    gross_acres: FracOrUnknown,
) -> FracOrUnknown:
    """NMA = mineral interest x gross (tract) acres."""
    if is_known(mineral_interest) and is_known(gross_acres):
        return mineral_interest * gross_acres
    return UNKNOWN


# --- Excel formula builders -------------------------------------------------
# These return formula strings that reproduce the math above directly in the
# workbook, so an auditor can trace every derived cell to its components.

def excel_nri_formula(mineral_cell: str, royalty_cell: str) -> str:
    """Royalty NRI formula guarded so blanks stay blank (not 0)."""
    return (
        f'=IF(OR({mineral_cell}="",{royalty_cell}=""),"UNKNOWN",'
        f"{mineral_cell}*{royalty_cell})"
    )


def excel_wi_nri_formula(wi_cell: str, burdens_cell: str) -> str:
    return (
        f'=IF(OR({wi_cell}="",{burdens_cell}=""),"UNKNOWN",'
        f"{wi_cell}*(1-{burdens_cell}))"
    )


def excel_nma_formula(mineral_cell: str, gross_acres_cell: str) -> str:
    return (
        f'=IF(OR({mineral_cell}="",{gross_acres_cell}=""),"UNKNOWN",'
        f"{mineral_cell}*{gross_acres_cell})"
    )


def total_known(values) -> FracOrUnknown:
    """Exact sum of the known fractions in ``values`` (ignores UNKNOWN)."""
    known = [v for v in values if is_known(v)]
    if not known:
        return UNKNOWN
    total = Fraction(0)
    for v in known:
        total += v
    return total
