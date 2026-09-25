"""Source-identity retention guard for reconciliation ledgers.

A source identity is deliberately distinct from an abstract-event stable key.
Cleanup, dedupe, OCR, or model review may change a source's disposition, but
must not silently delete a previously controlled source identity.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class SourceIdentityGuardReport:
    previous_count: int
    current_count: int
    expected_count: int | None = None
    missing_identities: list[str] = field(default_factory=list)
    duplicate_identities: list[str] = field(default_factory=list)
    blank_identities: int = 0
    missing_dispositions: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        count_ok = self.expected_count is None or self.current_count == self.expected_count
        return (
            count_ok
            and not self.missing_identities
            and not self.duplicate_identities
            and not self.blank_identities
            and not self.missing_dispositions
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "previous_count": self.previous_count,
            "current_count": self.current_count,
            "expected_count": self.expected_count,
            "missing_identities": self.missing_identities,
            "duplicate_identities": self.duplicate_identities,
            "blank_identities": self.blank_identities,
            "missing_dispositions": self.missing_dispositions,
            "passed": self.passed,
        }


def source_identity_guard(
    previous: Iterable[dict[str, Any]],
    current: Iterable[dict[str, Any]],
    *,
    identity_field: str = "source_identity",
    disposition_field: str = "disposition",
    expected_count: int | None = None,
) -> SourceIdentityGuardReport:
    """Fail closed if a controlled source vanishes or loses disposition."""

    previous_rows = list(previous)
    current_rows = list(current)

    previous_ids = [str(row.get(identity_field) or "").strip() for row in previous_rows]
    current_ids = [str(row.get(identity_field) or "").strip() for row in current_rows]

    previous_nonblank = {value for value in previous_ids if value}
    current_nonblank = [value for value in current_ids if value]
    current_set = set(current_nonblank)
    counts = Counter(current_nonblank)

    missing = sorted(previous_nonblank - current_set)
    duplicates = sorted(value for value, count in counts.items() if count > 1)
    blank_count = sum(1 for value in current_ids if not value)
    missing_dispositions = sorted(
        value
        for value, row in zip(current_ids, current_rows)
        if value and not str(row.get(disposition_field) or "").strip()
    )

    return SourceIdentityGuardReport(
        previous_count=len(previous_rows),
        current_count=len(current_rows),
        expected_count=expected_count,
        missing_identities=missing,
        duplicate_identities=duplicates,
        blank_identities=blank_count,
        missing_dispositions=missing_dispositions,
    )
