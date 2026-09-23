"""Canonical exact-interest math.

This module does not invent a second title authority. It exposes Horizon's
existing Fraction/Decimal engine so the trusted kernel and grocery pipeline
share one Grantor - Conveyed = Retained implementation.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_horizon_importable() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_horizon_importable()

from horizon.interest import (  # noqa: E402
    FULL,
    InterestError,
    Reconciliation,
    format_acres,
    format_fraction,
    net_acres,
    parse_acres,
    parse_interest,
    reconcile,
    sum_interests,
    try_parse_interest,
)

__all__ = [
    "FULL",
    "InterestError",
    "Reconciliation",
    "format_acres",
    "format_fraction",
    "net_acres",
    "parse_acres",
    "parse_interest",
    "reconcile",
    "sum_interests",
    "try_parse_interest",
    "conservation_holds",
]


def conservation_holds(values: list) -> bool:
    """True when exact interests sum to 8/8. Incomplete sets return False."""
    if len(values) < 2:
        return False
    try:
        return sum_interests(values) == FULL
    except InterestError:
        return False
