"""Field-level evidence, claims, and conflict records.

Models may detect candidates. They cannot resolve material conflicts and they
cannot overwrite a source-supported value with an inferred one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .database import DataBossDatabase


VALUE_STATES = (
    "known",
    "missing",
    "unreadable",
    "inapplicable",
    "inferred",
    "assumed",
    "externally_researched",
    "review_required",
)

_UNPROMOTED_STATES = frozenset(
    {"inferred", "assumed", "externally_researched", "review_required"}
)


@dataclass(frozen=True)
class EvidenceSpanRecord:
    evidence_span_id: int
    asset_version_id: int
    page: str
    snippet: str


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: int
    subject: str
    predicate: str
    value_text: str
    value_state: str


def add_evidence_span(
    db: DataBossDatabase,
    project_id: str,
    asset_version_id: int,
    *,
    snippet: str,
    page: str = "",
    char_start: int | None = None,
    char_end: int | None = None,
) -> EvidenceSpanRecord:
    span_id = db.execute(
        """
        INSERT INTO evidence_spans (
            project_id, asset_version_id, page, char_start, char_end, snippet
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (project_id, asset_version_id, page, char_start, char_end, snippet),
    )
    return EvidenceSpanRecord(
        evidence_span_id=span_id,
        asset_version_id=asset_version_id,
        page=page,
        snippet=snippet,
    )


def add_claim(
    db: DataBossDatabase,
    project_id: str,
    *,
    subject: str,
    predicate: str,
    value_text: str = "",
    value_state: str = "review_required",
    confidence: float | None = None,
) -> ClaimRecord:
    if value_state not in VALUE_STATES:
        raise ValueError(f"unknown value_state {value_state!r}")
    claim_id = db.execute(
        """
        INSERT INTO claims (
            project_id, subject, predicate, value_text, value_state, confidence
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (project_id, subject, predicate, value_text, value_state, confidence),
    )
    return ClaimRecord(
        claim_id=claim_id,
        subject=subject,
        predicate=predicate,
        value_text=value_text,
        value_state=value_state,
    )


def support_claim(db: DataBossDatabase, claim_id: int, evidence_span_id: int, rule_version: str = "1.0.0") -> int:
    return db.execute(
        """
        INSERT INTO claim_support (claim_id, evidence_span_id, rule_version)
        VALUES (?, ?, ?)
        """,
        (claim_id, evidence_span_id, rule_version),
    )


def open_conflict(
    db: DataBossDatabase,
    project_id: str,
    claim_id_a: int,
    claim_id_b: int,
    *,
    material: bool = True,
) -> int:
    return db.execute(
        """
        INSERT INTO conflicts (
            project_id, claim_id_a, claim_id_b, material, resolution_state
        ) VALUES (?, ?, ?, ?, 'OPEN')
        """,
        (project_id, claim_id_a, claim_id_b, 1 if material else 0),
    )


def resolve_conflict(
    db: DataBossDatabase,
    conflict_id: int,
    *,
    reviewer_id: str,
    notes: str = "",
) -> None:
    row = db.fetchone("SELECT project_id FROM conflicts WHERE id = ?", (conflict_id,))
    if row is None:
        raise ValueError(f"unknown conflict {conflict_id}")
    if not reviewer_id.strip():
        raise ValueError("material conflicts require a qualified human reviewer id")
    db.execute(
        """
        UPDATE conflicts
           SET resolution_state = 'RESOLVED', resolved_by = ?
         WHERE id = ?
        """,
        (reviewer_id, conflict_id),
    )
    db.audit(
        str(row["project_id"]),
        "conflict.resolved",
        "conflict",
        str(conflict_id),
        json.dumps({"reviewer_id": reviewer_id, "notes": notes}, sort_keys=True),
    )


def cannot_promote_inferred(value_state: str) -> bool:
    return value_state in _UNPROMOTED_STATES
