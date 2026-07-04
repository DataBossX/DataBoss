"""Exact interest reconciliation for title chains.

Mission Interest Logic:  ``Grantor - Conveyed = Retained``, performed with
**Fraction and Decimal math only -- no floats**. A float such as ``0.1`` cannot
represent common mineral fractions (1/3, 1/16, 5/128 ...) exactly; over a long
chain those errors compound and produce a fabricated net-acre balance. We refuse
to do that: every quantity is an exact :class:`fractions.Fraction`, parsed from
fractions, decimals (via :class:`decimal.Decimal`), or percentages.

Where a balance cannot be determined from the files (an unknown grantor
interest, or a conveyance that exceeds what the grantor holds), we do **not**
invent a balance -- we return an ``examiner_review`` result so the tract carries
a "Needs Examiner Review" tag downstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import List, Optional, Union

Number = Union[str, int, Fraction, Decimal]

# A whole mineral estate is 8/8 == 1. Kept explicit for readability in chains.
FULL = Fraction(1, 1)

_FRACTION_RE = re.compile(r"^\s*(-?\d+)\s*/\s*(\d+)\s*$")
_MIXED_RE = re.compile(r"^\s*(-?\d+)\s+(\d+)\s*/\s*(\d+)\s*$")
_PERCENT_RE = re.compile(r"^\s*(-?[\d.]+)\s*%\s*$")
# "an undivided 1/2", "1/2 of 8/8", "1/16th" ... strip decorative words.
_DECOR_RE = re.compile(r"\b(an?|undivided|interest|of|the|mineral|royalty)\b", re.I)
_ORDINAL_RE = re.compile(r"(\d)(st|nd|rd|th)\b", re.I)


class InterestError(ValueError):
    """Raised when a string cannot be parsed as an exact interest."""


def parse_interest(value: Optional[Number]) -> Fraction:
    """Parse ``value`` into an exact :class:`Fraction`.

    Accepts fractions ("1/2", "5/128"), mixed numbers ("1 1/2"), decimals
    ("0.5" -> exact via Decimal), percentages ("12.5%"), and "x of y"
    ("1/2 of 8/8"). Raises :class:`InterestError` on anything ambiguous rather
    than guessing.
    """
    if value is None:
        raise InterestError("cannot parse interest from None")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Decimal):
        return Fraction(value)

    s = str(value).strip()
    if not s:
        raise InterestError("cannot parse interest from empty string")

    # "1/2 of 8/8" -> product of the two fractions.
    low = s.lower()
    if " of " in low:
        left, right = low.split(" of ", 1)
        return parse_interest(left) * parse_interest(right)

    cleaned = _ORDINAL_RE.sub(r"\1", s)
    cleaned = _DECOR_RE.sub(" ", cleaned).strip()

    m = _PERCENT_RE.match(cleaned)
    if m:
        return Fraction(Decimal(m.group(1))) / 100

    m = _MIXED_RE.match(cleaned)
    if m:
        whole, num, den = (int(g) for g in m.groups())
        if den == 0:
            raise InterestError(f"zero denominator in {value!r}")
        sign = -1 if whole < 0 else 1
        return Fraction(whole) + sign * Fraction(num, den)

    m = _FRACTION_RE.match(cleaned)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        if den == 0:
            raise InterestError(f"zero denominator in {value!r}")
        return Fraction(num, den)

    # bare decimal / integer
    try:
        return Fraction(Decimal(cleaned))
    except (InvalidOperation, ValueError) as exc:
        raise InterestError(f"unparseable interest {value!r}") from exc


def try_parse_interest(value: Optional[Number]) -> Optional[Fraction]:
    """Like :func:`parse_interest` but returns ``None`` instead of raising."""
    try:
        return parse_interest(value)
    except InterestError:
        return None


def net_acres(interest: Number, gross_acres: Number) -> Fraction:
    """Net acres = interest fraction x gross acres, exactly.

    ``gross_acres`` is parsed through :class:`Decimal` so "160.00" stays exact.
    Returns a :class:`Fraction`; call :func:`format_acres` to display.
    """
    frac = parse_interest(interest) if not isinstance(interest, Fraction) else interest
    if isinstance(gross_acres, Fraction):
        gross = gross_acres
    elif isinstance(gross_acres, Decimal):
        gross = Fraction(gross_acres)
    else:
        gross = Fraction(Decimal(str(gross_acres)))
    return frac * gross


@dataclass
class Reconciliation:
    """Result of a single ``Grantor - Conveyed = Retained`` reconciliation."""

    grantor: Optional[Fraction]
    conveyed: Optional[Fraction]
    retained: Optional[Fraction]
    status: str  # "balanced" | "examiner_review" | "over_conveyance"
    note: str = ""

    @property
    def needs_review(self) -> bool:
        return self.status != "balanced"

    def as_dict(self) -> dict:
        def fmt(f: Optional[Fraction]) -> str:
            return format_fraction(f) if f is not None else ""

        return {
            "grantor_interest": fmt(self.grantor),
            "conveyed_interest": fmt(self.conveyed),
            "retained_interest": fmt(self.retained),
            "status": self.status,
            "note": self.note,
        }


def reconcile(grantor: Optional[Number], conveyed: Optional[Number]) -> Reconciliation:
    """Absolute interest reconciliation: ``retained = grantor - conveyed``.

    * Unknown grantor or conveyed interest -> ``examiner_review`` (no guessing).
    * Conveyed exceeds grantor's holding -> ``over_conveyance`` (impossible to
      have retained a negative interest; flag rather than fabricate).
    """
    g = try_parse_interest(grantor) if grantor is not None and str(grantor).strip() else None
    c = try_parse_interest(conveyed) if conveyed is not None and str(conveyed).strip() else None

    if g is None or c is None:
        missing = []
        if g is None:
            missing.append("grantor interest")
        if c is None:
            missing.append("conveyed interest")
        return Reconciliation(
            grantor=g, conveyed=c, retained=None,
            status="examiner_review",
            note="Undetermined net balance: missing " + ", ".join(missing),
        )

    retained = g - c
    if retained < 0:
        return Reconciliation(
            grantor=g, conveyed=c, retained=retained,
            status="over_conveyance",
            note=(f"Grantor conveyed {format_fraction(c)} but only held "
                  f"{format_fraction(g)} (over-conveyance of "
                  f"{format_fraction(-retained)})."),
        )
    return Reconciliation(
        grantor=g, conveyed=c, retained=retained,
        status="balanced",
        note="",
    )


def format_fraction(frac: Fraction) -> str:
    """Render a fraction as "num/den" (or a bare integer)."""
    if frac.denominator == 1:
        return str(frac.numerator)
    return f"{frac.numerator}/{frac.denominator}"


def format_acres(frac: Fraction, places: int = 4) -> str:
    """Render an (exact) acre quantity as a fixed-point decimal string.

    Uses Decimal quantization for a clean display value while the underlying
    quantity stays exact -- display rounding never feeds back into the math.
    """
    q = Decimal(frac.numerator) / Decimal(frac.denominator)
    exp = Decimal(1).scaleb(-places)  # 10^-places
    return str(q.quantize(exp))


def sum_interests(values: List[Number]) -> Fraction:
    """Exact sum of a list of interests (e.g. all fractions conveyed out)."""
    total = Fraction(0)
    for v in values:
        total += parse_interest(v)
    return total
