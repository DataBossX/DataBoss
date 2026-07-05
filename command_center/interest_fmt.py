"""Tiny display helpers that tolerate ``None`` (unknown) quantities."""

from __future__ import annotations

from fractions import Fraction
from typing import Optional

from horizon.interest import format_acres, format_fraction


def fmt_acres(frac: Optional[Fraction], places: int = 4) -> str:
    """Format an exact acre quantity, or ``"?"`` when it is undetermined."""
    return format_acres(frac, places) if frac is not None else "?"


def fmt_fraction(frac: Optional[Fraction]) -> str:
    """Format an exact interest fraction, or ``"?"`` when it is undetermined."""
    return format_fraction(frac) if frac is not None else "?"
