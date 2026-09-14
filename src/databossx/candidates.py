"""Candidate comparison that never auto-resolves material conflicts.

Majority agreement is not evidence. A value without supporting source hashes
is UNSUPPORTED even when producers agree. Conflicts stay conflicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .hashing import sha256_bytes
from .receipts import canonical_dumps


AGREE = "AGREE"
CONFLICT = "CONFLICT"
MISSING = "MISSING"
UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    producer: str
    values: Mapping[str, Any]
    evidence_hashes: Mapping[str, Sequence[str]] = field(default_factory=dict)
    schema_valid: bool = True


@dataclass(frozen=True)
class FieldObservation:
    candidate_id: str
    producer: str
    value: Any
    evidence_hashes: tuple[str, ...]


@dataclass(frozen=True)
class FieldComparison:
    field: str
    status: str
    observations: tuple[FieldObservation, ...]
    distinct_supported_values: tuple[str, ...]

    @property
    def is_conflict(self) -> bool:
        return self.status == CONFLICT


@dataclass(frozen=True)
class ComparisonReport:
    subject_key: str
    fields: tuple[FieldComparison, ...]
    winner_candidate_id: None = None
    resolution: str = "human_required_if_material"

    @property
    def conflict_count(self) -> int:
        return sum(1 for item in self.fields if item.is_conflict)

    @property
    def unsupported_count(self) -> int:
        return sum(1 for item in self.fields if item.status == UNSUPPORTED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_count": self.conflict_count,
            "fields": [
                {
                    "distinct_supported_values": list(item.distinct_supported_values),
                    "field": item.field,
                    "observations": [
                        {
                            "candidate_id": obs.candidate_id,
                            "evidence_hashes": list(obs.evidence_hashes),
                            "producer": obs.producer,
                            "value": obs.value,
                        }
                        for obs in item.observations
                    ],
                    "status": item.status,
                }
                for item in self.fields
            ],
            "resolution": self.resolution,
            "subject_key": self.subject_key,
            "unsupported_count": self.unsupported_count,
            "winner_candidate_id": self.winner_candidate_id,
        }


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    return canonical_dumps(value)


def _evidence(candidate: Candidate, field: str) -> tuple[str, ...]:
    raw = candidate.evidence_hashes.get(field, ())
    return tuple(item for item in raw if item)


def compare_candidates(
    subject_key: str,
    candidates: Iterable[Candidate],
) -> ComparisonReport:
    catalog = list(candidates)
    fields = sorted({field for candidate in catalog for field in candidate.values})
    comparisons: list[FieldComparison] = []
    for field in fields:
        observations = [
            FieldObservation(
                candidate_id=candidate.candidate_id,
                producer=candidate.producer,
                value=candidate.values.get(field),
                evidence_hashes=_evidence(candidate, field),
            )
            for candidate in catalog
            if field in candidate.values
        ]
        missing = len(observations) != len(catalog)
        supported = [obs for obs in observations if obs.evidence_hashes]
        unsupported = [obs for obs in observations if not obs.evidence_hashes]
        distinct = tuple(sorted({_normalize(obs.value) for obs in supported}))
        if unsupported and not supported:
            status = UNSUPPORTED
        elif unsupported and supported:
            # A bare assertion sitting beside evidenced values is not a vote.
            status = UNSUPPORTED if len(distinct) <= 1 else CONFLICT
        elif missing:
            status = MISSING if len(distinct) <= 1 else CONFLICT
        elif len(distinct) > 1:
            status = CONFLICT
        else:
            status = AGREE
        comparisons.append(
            FieldComparison(
                field=field,
                status=status,
                observations=tuple(observations),
                distinct_supported_values=distinct,
            )
        )
    return ComparisonReport(subject_key=subject_key, fields=tuple(comparisons))


def comparison_hash(report: ComparisonReport) -> str:
    return sha256_bytes(canonical_dumps(report.to_dict()).encode("utf-8"))
