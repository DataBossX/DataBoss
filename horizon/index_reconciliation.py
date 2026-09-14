"""Reconcile master, PDF, and handwritten indexes with field provenance.

The gate does not open Drive, invent rows, or mutate a workbook. It consumes
an isolated packet, scores required fields, and emits fill proposals only
when at least two named sources agree. ``technical_pass`` is packet
consistency, not package release.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .isolated_delta import IsolatedDeltaError, parse_row_key
from .stable_key import StableKeyError

PACKET_SCHEMA_ID = "dbx.index_reconciliation_packet"
PACKET_SCHEMA_VERSION = "1.0"
RECEIPT_SCHEMA_ID = "dbx.index_reconciliation_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
SOURCE_NAMES = ("master", "pdf_index", "handwritten_index")
REQUIRED_FIELDS = (
    "document_type",
    "grantor",
    "grantee",
    "recorded_date",
    "legal_description",
)
REQUIRED_PACKET_KEYS = {
    "schema_id",
    "schema_version",
    "packet_id",
    "master",
    "pdf_index",
    "handwritten_index",
    "candidate_rows",
    "expected_counts",
    "orphan_allowlist",
}
REQUIRED_FACE_KEYS = {
    "stable_key",
    "source_sha256",
    "page",
    "crop_id",
    "fields",
}
REQUIRED_ALLOW_KEYS = {"stable_key", "present_in", "source_sha256"}
COUNT_KEYS = (*SOURCE_NAMES, "candidate_rows")
NEWLINE_FIELDS = {"grantor", "grantee", "legal_description"}


class IndexReconciliationError(ValueError):
    """Raised when an index-reconciliation packet is unsafe."""


@dataclass(frozen=True)
class FaceRow:
    source: str
    stable_key: str
    source_sha256: str
    page: int
    crop_id: str
    fields: Dict[str, str]


@dataclass(frozen=True)
class OrphanAllow:
    stable_key: str
    present_in: Tuple[str, ...]
    source_sha256: str


@dataclass(frozen=True)
class FieldScore:
    stable_key: str
    field: str
    confidence: str
    consensus_value: str
    candidate_value: str
    agreeing_sources: List[str]
    conflict_values: Dict[str, List[str]]
    provenance: List[Dict[str, object]]
    eligible_for_isolated_delta: bool
    status: str


@dataclass
class IndexReconciliationReceipt:
    generated_utc: str
    packet_id: str
    source_counts: Dict[str, int]
    unique_keys: Dict[str, int]
    field_scores: List[FieldScore]
    proposed_deltas: List[Dict[str, object]]
    issues: List[str]
    blank_required_count: int
    conflict_count: int
    low_confidence_blank_count: int
    technical_pass: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "Proposals require a writer-held isolated delta apply",
            "technical_pass is not package release",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise IndexReconciliationError(f"{label} must be a single-line string")
    return value.strip()


def _require_sha256(value: object, label: str) -> str:
    digest = value.casefold() if isinstance(value, str) else ""
    if not _is_sha256(digest):
        raise IndexReconciliationError(f"{label} has an invalid source_sha256")
    return digest


def _require_fields(raw: object, label: str) -> Dict[str, str]:
    if not isinstance(raw, dict) or set(raw) != set(REQUIRED_FIELDS):
        raise IndexReconciliationError(f"{label} must contain only required fields")
    fields: Dict[str, str] = {}
    for name in REQUIRED_FIELDS:
        value = raw[name]
        if value is None:
            fields[name] = ""
            continue
        if not isinstance(value, str):
            raise IndexReconciliationError(f"{label}.{name} must be a string")
        if name not in NEWLINE_FIELDS and ("\n" in value or "\r" in value):
            raise IndexReconciliationError(
                f"{label}.{name} must be a single-line string"
            )
        if ",," in value:
            raise IndexReconciliationError(f"{label}.{name} value is unsafe")
        fields[name] = value.strip()
    return fields


def _parse_faces(raw_rows: object, source: str) -> List[FaceRow]:
    if not isinstance(raw_rows, list):
        raise IndexReconciliationError(f"{source} must be a list")
    rows: List[FaceRow] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, dict) or set(raw) != REQUIRED_FACE_KEYS:
            raise IndexReconciliationError(f"{source}[{index}] has invalid fields")
        try:
            _, lookup = parse_row_key(raw["stable_key"])
        except IsolatedDeltaError as exc:
            raise IndexReconciliationError(
                f"{source}[{index}] stable_key is invalid"
            ) from exc
        if lookup in seen:
            raise IndexReconciliationError(
                f"{source} has duplicate stable_key {lookup}"
            )
        seen.add(lookup)
        page = raw["page"]
        if type(page) is not int or page < 1:
            raise IndexReconciliationError(
                f"{source}[{index}] page must be an integer >= 1"
            )
        rows.append(
            FaceRow(
                source=source,
                stable_key=lookup,
                source_sha256=_require_sha256(
                    raw["source_sha256"], f"{source}[{index}]"
                ),
                page=page,
                crop_id=_require_text(raw["crop_id"], "crop_id"),
                fields=_require_fields(raw["fields"], f"{source}[{index}].fields"),
            )
        )
    return rows


def parse_index_packet(
    payload: Dict[str, object],
) -> tuple[str, Dict[str, List[FaceRow]], List[FaceRow], Dict[str, int], List[OrphanAllow]]:
    if set(payload) != REQUIRED_PACKET_KEYS:
        raise IndexReconciliationError(
            "Index reconciliation packet has invalid top-level fields"
        )
    if (
        payload["schema_id"] != PACKET_SCHEMA_ID
        or payload["schema_version"] != PACKET_SCHEMA_VERSION
    ):
        raise IndexReconciliationError("Index reconciliation schema is invalid")
    packet_id = _require_text(payload["packet_id"], "packet_id")
    sources = {
        name: _parse_faces(payload[name], name) for name in SOURCE_NAMES
    }
    if not any(sources[name] for name in SOURCE_NAMES):
        raise IndexReconciliationError("At least one source index must have rows")
    candidates = _parse_faces(payload["candidate_rows"], "candidate_rows")
    raw_counts = payload["expected_counts"]
    if not isinstance(raw_counts, dict) or set(raw_counts) != set(COUNT_KEYS):
        raise IndexReconciliationError("expected_counts has invalid fields")
    expected: Dict[str, int] = {}
    for name in COUNT_KEYS:
        value = raw_counts[name]
        if type(value) is not int or isinstance(value, bool) or value < 0:
            raise IndexReconciliationError(
                f"expected_counts.{name} must be a non-negative integer"
            )
        expected[name] = value
    raw_allow = payload["orphan_allowlist"]
    if not isinstance(raw_allow, list):
        raise IndexReconciliationError("orphan_allowlist must be a list")
    allow: List[OrphanAllow] = []
    seen_allow: set[str] = set()
    for index, raw in enumerate(raw_allow):
        if not isinstance(raw, dict) or set(raw) != REQUIRED_ALLOW_KEYS:
            raise IndexReconciliationError(
                f"orphan_allowlist[{index}] has invalid fields"
            )
        try:
            _, lookup = parse_row_key(raw["stable_key"])
        except IsolatedDeltaError as exc:
            raise IndexReconciliationError(
                f"orphan_allowlist[{index}] stable_key is invalid"
            ) from exc
        if lookup in seen_allow:
            raise IndexReconciliationError(
                f"orphan_allowlist stable_key is duplicated: {lookup}"
            )
        seen_allow.add(lookup)
        present = raw["present_in"]
        if not isinstance(present, list) or not present:
            raise IndexReconciliationError(
                f"orphan_allowlist[{index}] present_in must be a non-empty list"
            )
        names = tuple(_require_text(item, "present_in") for item in present)
        if any(name not in SOURCE_NAMES for name in names):
            raise IndexReconciliationError(
                f"orphan_allowlist[{index}] present_in has an unknown source"
            )
        if len(set(names)) != len(names):
            raise IndexReconciliationError(
                f"orphan_allowlist[{index}] present_in is duplicated"
            )
        if set(names) == set(SOURCE_NAMES):
            raise IndexReconciliationError(
                f"orphan_allowlist[{index}] is not an orphan"
            )
        allow.append(
            OrphanAllow(
                stable_key=lookup,
                present_in=tuple(sorted(names)),
                source_sha256=_require_sha256(
                    raw["source_sha256"], f"orphan_allowlist[{index}]"
                ),
            )
        )
    return packet_id, sources, candidates, expected, allow


def _index_by_key(rows: Sequence[FaceRow]) -> Dict[str, FaceRow]:
    return {row.stable_key: row for row in rows}


def _score_field(
    key: str,
    field_name: str,
    source_rows: Dict[str, Optional[FaceRow]],
    candidate: Optional[FaceRow],
) -> FieldScore:
    by_value: Dict[str, List[str]] = defaultdict(list)
    provenance: List[Dict[str, object]] = []
    for name, row in source_rows.items():
        if row is None:
            continue
        value = row.fields.get(field_name, "")
        if not value:
            continue
        by_value[value].append(name)
        provenance.append(
            {
                "source": name,
                "source_sha256": row.source_sha256,
                "page": row.page,
                "crop_id": row.crop_id,
                "value": value,
            }
        )
    candidate_value = ""
    if candidate is not None:
        candidate_value = candidate.fields.get(field_name, "")
    if len(by_value) > 1:
        confidence = "conflict"
        consensus = ""
        agreeing: List[str] = []
        status = "conflict"
        eligible = False
    elif not by_value:
        confidence = "blank"
        consensus = ""
        agreeing = []
        status = "no_source"
        eligible = False
    else:
        consensus, agreeing = next(iter(by_value.items()))
        present = len(agreeing)
        confidence = {3: "high", 2: "medium", 1: "low"}[present]
        if candidate_value and candidate_value != consensus:
            status = "candidate_differs"
            eligible = False
            confidence = "conflict"
        elif candidate_value == consensus:
            status = "already_present"
            eligible = False
        elif confidence in {"high", "medium"}:
            status = "proposed"
            eligible = True
        else:
            status = "low_confidence"
            eligible = False
    return FieldScore(
        stable_key=key,
        field=field_name,
        confidence=confidence,
        consensus_value=consensus,
        candidate_value=candidate_value,
        agreeing_sources=sorted(agreeing),
        conflict_values={value: sorted(names) for value, names in by_value.items()}
        if confidence == "conflict"
        else {},
        provenance=provenance,
        eligible_for_isolated_delta=eligible,
        status=status,
    )


def reconcile_indexes(payload: Dict[str, object]) -> IndexReconciliationReceipt:
    packet_id, sources, candidates, expected, allow = parse_index_packet(payload)
    issues: List[str] = []
    actual_counts = {
        name: len(sources[name]) for name in SOURCE_NAMES
    }
    actual_counts["candidate_rows"] = len(candidates)
    for name, expected_count in expected.items():
        if actual_counts[name] != expected_count:
            issues.append(
                f"count mismatch {name}: expected {expected_count}, "
                f"found {actual_counts[name]}"
            )
    by_source = {name: _index_by_key(sources[name]) for name in SOURCE_NAMES}
    candidate_by_key = _index_by_key(candidates)
    all_keys = set(candidate_by_key)
    for name in SOURCE_NAMES:
        all_keys.update(by_source[name])
    allow_by_key = {item.stable_key: item for item in allow}
    for key in sorted(all_keys):
        present = tuple(
            sorted(name for name in SOURCE_NAMES if key in by_source[name])
        )
        allowed = allow_by_key.get(key)
        if present != SOURCE_NAMES:
            if allowed is None:
                issues.append(
                    f"orphan key {key} present_in={list(present)}"
                )
            elif allowed.present_in != present:
                issues.append(
                    f"orphan allowlist {key} expected {list(allowed.present_in)}, "
                    f"found {list(present)}"
                )
        elif allowed is not None:
            issues.append(f"orphan allowlist {key} is present in every source")
        if key not in candidate_by_key:
            issues.append(f"source key {key} is missing from candidate_rows")
        if key in candidate_by_key and not present:
            issues.append(
                f"candidate key {key} is not present in master, PDF, or handwritten"
            )
    scores: List[FieldScore] = []
    proposals: List[Dict[str, object]] = []
    for key in sorted(all_keys):
        source_rows = {name: by_source[name].get(key) for name in SOURCE_NAMES}
        candidate = candidate_by_key.get(key)
        for field_name in REQUIRED_FIELDS:
            score = _score_field(key, field_name, source_rows, candidate)
            scores.append(score)
            if score.eligible_for_isolated_delta:
                first = score.provenance[0]
                proposals.append(
                    {
                        "row_key": key,
                        "field": field_name,
                        "value": score.consensus_value,
                        "source_sha256": first["source_sha256"],
                        "page": first["page"],
                        "crop_id": first["crop_id"],
                        "replace": False,
                        "confidence": score.confidence,
                        "agreeing_sources": score.agreeing_sources,
                    }
                )
    blank_required = sum(
        1
        for score in scores
        if score.field in REQUIRED_FIELDS and not score.candidate_value
    )
    conflicts = sum(1 for score in scores if score.confidence == "conflict")
    low_blanks = sum(
        1
        for score in scores
        if score.status == "low_confidence" and not score.candidate_value
    )
    if conflicts:
        issues.append(f"{conflicts} required-field conflicts")
    unique_keys = {
        name: len(by_source[name]) for name in SOURCE_NAMES
    }
    unique_keys["candidate_rows"] = len(candidate_by_key)
    return IndexReconciliationReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        packet_id=packet_id,
        source_counts=actual_counts,
        unique_keys=unique_keys,
        field_scores=scores,
        proposed_deltas=proposals,
        issues=issues,
        blank_required_count=blank_required,
        conflict_count=conflicts,
        low_confidence_blank_count=low_blanks,
        technical_pass=not issues,
    )


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndexReconciliationError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise IndexReconciliationError(f"{path} must contain a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile master, PDF, and handwritten indexes and score "
            "required fields. Does not apply fills."
        )
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        receipt = reconcile_indexes(_load_json(args.packet))
        args.output.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (OSError, IndexReconciliationError, IsolatedDeltaError, StableKeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "technical_pass": receipt.technical_pass,
                "proposed_deltas": len(receipt.proposed_deltas),
                "conflict_count": receipt.conflict_count,
                "blank_required_count": receipt.blank_required_count,
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
