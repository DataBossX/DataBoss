"""Validated, ordered security-classification lattice.

Classifications are totally ordered from least to most restrictive. The lattice
is used to (a) validate any classification string entering the control plane and
(b) guarantee that identical content registered in a stricter project is never
downgraded when it is also registered in a more permissive one.
"""

from __future__ import annotations

from typing import Iterable

# Least restrictive first. Index is the severity rank.
CLASSIFICATIONS: tuple[str, ...] = (
    "PUBLIC",
    "INTERNAL",
    "CONFIDENTIAL",
    "RESTRICTED",
    "SECRET",
)

# Content the control plane always treats as at least confidential.
CONFIDENTIAL = "CONFIDENTIAL"

_RANK = {name: index for index, name in enumerate(CLASSIFICATIONS)}


class ClassificationError(ValueError):
    """Raised for an unknown or malformed classification value."""


def normalize(value: str) -> str:
    """Return the canonical (upper-cased, trimmed) classification or raise."""
    if not isinstance(value, str):
        raise ClassificationError(f"classification must be a string: {value!r}")
    candidate = value.strip().upper()
    if candidate not in _RANK:
        raise ClassificationError(
            f"unknown classification {value!r}; expected one of {', '.join(CLASSIFICATIONS)}"
        )
    return candidate


def rank(value: str) -> int:
    """Severity rank; higher means more restrictive."""
    return _RANK[normalize(value)]


def is_at_least(value: str, floor: str) -> bool:
    return rank(value) >= rank(floor)


def strictest(*values: str) -> str:
    """Return the most restrictive classification among ``values``."""
    if not values:
        raise ClassificationError("strictest() requires at least one classification")
    return max((normalize(v) for v in values), key=lambda v: _RANK[v])


def max_classification(values: Iterable[str]) -> str:
    materialized = list(values)
    if not materialized:
        raise ClassificationError("max_classification() requires at least one value")
    return strictest(*materialized)


def ensure_not_downgraded(existing: str | None, incoming: str) -> str:
    """Return the classification to persist, never below ``existing``.

    Registering identical content in a more permissive project must not lower the
    effective classification set by a stricter project.
    """
    incoming = normalize(incoming)
    if existing is None:
        return incoming
    return strictest(existing, incoming)
