"""Portfolio QA dashboard schema and fail-closed rules.

The dashboard is a read-only projection of cited receipts. It does not
examine abstracts, does not invent client facts, and does not coerce
UNKNOWN into a numeric zero.
"""

from __future__ import annotations

REQUIRED_COLUMNS: tuple[str, ...] = (
    "package",
    "latest_verified_receipt_url_date",
    "county_denominator",
    "county_matched",
    "missing_faces",
    "federal_pages",
    "federal_event_coverage",
    "source_contradiction",
    "writer_gate",
    "native_page_qa",
    "exact_membership",
    "owner_action",
    "next_unique_action",
    "status",
    "confidence",
)

# Hold types stay distinct. A source hold is an instrument/face gap.
# A control/custody hold is writer, filing, release, or package-location.
HOLD_TYPES: frozenset[str] = frozenset(
    {"source_hold", "control_hold", "custody_hold", "none", "UNKNOWN"}
)

EVIDENCE_CLASSES: frozenset[str] = frozenset(
    {"SOURCE", "RECEIPT", "MODEL", "UNKNOWN", "RECEIPT_CONTRADICTION", "SOURCE_PIXEL"}
)

# Ranking: source evidence outranks receipts; receipts outrank model conclusions.
EVIDENCE_RANK: dict[str, int] = {
    "SOURCE": 40,
    "SOURCE_PIXEL": 40,
    "RECEIPT": 20,
    "RECEIPT_CONTRADICTION": 20,
    "MODEL": 10,
    "UNKNOWN": 0,
}

FROZEN_BENCHMARK_STATUSES: frozenset[str] = frozenset(
    {"FROZEN_BENCHMARK", "FROZEN_DONOR"}
)

UNKNOWN_TOKEN = "UNKNOWN"

# Tokens that must never replace UNKNOWN during aggregation.
ZERO_COERCIONS: frozenset[str] = frozenset(
    {"0", "0.0", "0/0", "none", "n/a", "na", "null", "-", ""}
)


def is_unknown(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.upper() == UNKNOWN_TOKEN


def refuse_zero_coercion(value: object) -> str:
    """Return UNKNOWN unchanged. Never convert UNKNOWN to zero."""
    if is_unknown(value):
        return UNKNOWN_TOKEN
    return str(value).strip()


def prefer_evidence(left_class: str, right_class: str) -> str:
    """Return the higher-ranked evidence class. UNKNOWN never wins a fill."""
    left = left_class if left_class in EVIDENCE_RANK else UNKNOWN_TOKEN
    right = right_class if right_class in EVIDENCE_RANK else UNKNOWN_TOKEN
    return left if EVIDENCE_RANK[left] >= EVIDENCE_RANK[right] else right


def is_frozen_benchmark(status: str) -> bool:
    return str(status).strip().upper() in FROZEN_BENCHMARK_STATUSES
