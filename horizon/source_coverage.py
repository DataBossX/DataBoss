"""OCR-manifest coverage vs source-pixel review coverage.

OCR success is never source verification. A record that has been OCR'd but
not read against the actual source pixels is HOLD, not verified --
regardless of how complete or confident the OCR pass was. UNKNOWN is not
zero: every summary carries explicit counts for OCR-only holds, no-review
holds, and unresolved records rather than silently folding them into a
single coverage percentage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

PIXEL_VERIFIED = "PIXEL_VERIFIED"
OCR_ONLY_HOLD = "OCR_ONLY_HOLD"
NO_REVIEW_HOLD = "NO_REVIEW_HOLD"
UNRESOLVED = "UNRESOLVED"

STATUSES = frozenset({PIXEL_VERIFIED, OCR_ONLY_HOLD, NO_REVIEW_HOLD, UNRESOLVED})


def classify_source(record: dict[str, Any]) -> str:
    """Classify one source record's review status.

    A record is only ``PIXEL_VERIFIED`` when ``pixel_reviewed`` is true.
    ``ocr_reviewed`` alone -- however complete that OCR pass was -- can
    never promote a record past HOLD.
    """
    disposition = str(record.get("disposition") or "").strip().upper()
    if not disposition or disposition == "UNRESOLVED":
        return UNRESOLVED
    if bool(record.get("pixel_reviewed")):
        return PIXEL_VERIFIED
    if bool(record.get("ocr_reviewed")):
        return OCR_ONLY_HOLD
    return NO_REVIEW_HOLD


@dataclass
class CoverageSummary:
    total: int
    pixel_verified: int
    ocr_only_hold: int
    no_review_hold: int
    unresolved: int
    by_identity: dict[str, str] = field(default_factory=dict)

    @property
    def hold_count(self) -> int:
        """Non-verified, non-unresolved records. Not folded into "resolved"."""
        return self.ocr_only_hold + self.no_review_hold

    @property
    def unresolved_or_hold_count(self) -> int:
        return self.unresolved + self.hold_count

    @property
    def fully_pixel_verified(self) -> bool:
        """True only when every record is individually pixel-verified."""
        return self.total > 0 and self.pixel_verified == self.total

    @property
    def ocr_coverage_ratio(self) -> float:
        """Share of records with *some* OCR pass -- locator coverage, not proof."""
        if self.total == 0:
            return 0.0
        ocr_touched = self.pixel_verified + self.ocr_only_hold
        return ocr_touched / self.total

    @property
    def pixel_coverage_ratio(self) -> float:
        if self.total == 0:
            return 0.0
        return self.pixel_verified / self.total

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "pixel_verified": self.pixel_verified,
            "ocr_only_hold": self.ocr_only_hold,
            "no_review_hold": self.no_review_hold,
            "unresolved": self.unresolved,
            "hold_count": self.hold_count,
            "unresolved_or_hold_count": self.unresolved_or_hold_count,
            "fully_pixel_verified": self.fully_pixel_verified,
            "ocr_coverage_ratio": self.ocr_coverage_ratio,
            "pixel_coverage_ratio": self.pixel_coverage_ratio,
        }


def coverage_summary(
    records: Iterable[dict[str, Any]],
    *,
    identity_field: str = "source_identity",
) -> CoverageSummary:
    """Summarize OCR vs pixel review coverage across *records*."""
    rows = list(records)
    counts = {PIXEL_VERIFIED: 0, OCR_ONLY_HOLD: 0, NO_REVIEW_HOLD: 0, UNRESOLVED: 0}
    by_identity: dict[str, str] = {}
    for row in rows:
        status = classify_source(row)
        counts[status] += 1
        identity = str(row.get(identity_field) or "").strip()
        if identity:
            by_identity[identity] = status
    return CoverageSummary(
        total=len(rows),
        pixel_verified=counts[PIXEL_VERIFIED],
        ocr_only_hold=counts[OCR_ONLY_HOLD],
        no_review_hold=counts[NO_REVIEW_HOLD],
        unresolved=counts[UNRESOLVED],
        by_identity=by_identity,
    )
