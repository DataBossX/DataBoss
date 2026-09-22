"""Compare index occurrences, unique-key ledgers, and candidate rows.

This module does not read client Drive/PC files and does not mutate a
canonical workbook. It consumes an isolated JSON packet, reports count and
hash contradictions, and emits a resume cursor so closed same-hash items are
not re-reviewed blindly.

``technical_pass`` means only that the supplied packet has no ledger
contradiction. It is not package release, legal correctness, or a PASS claim
for a section abstract.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

PACKET_SCHEMA_ID = "dbx.occurrence_packet"
PACKET_SCHEMA_VERSION = "1.0"
RECEIPT_SCHEMA_ID = "dbx.occurrence_ledger_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
CURSOR_SCHEMA_ID = "dbx.occurrence_resume_cursor"
CURSOR_SCHEMA_VERSION = "1.0"
RISK_VALUES = ("closed_same_hash", "disputed", "high_risk", "novel")
CLOSED_RISK = "closed_same_hash"
REQUIRED_PACKET_KEYS = {
    "schema_id",
    "schema_version",
    "packet_id",
    "occurrences",
    "unique_key_ledger",
    "candidate_rows",
    "allowlist",
}
REQUIRED_OCCURRENCE_KEYS = {
    "occurrence_id",
    "stable_key",
    "source_sha256",
    "page",
    "crop_id",
    "fields",
    "risk",
}
REQUIRED_KEY_RECORD_KEYS = {"stable_key", "source_sha256"}
REQUIRED_ROW_KEYS = {"row_id", "stable_key", "source_sha256", "fields"}
REQUIRED_ALLOWLIST_KEYS = {"stable_key", "source_sha256", "status"}
REQUIRED_CURSOR_KEYS = {
    "schema_id",
    "schema_version",
    "packet_id",
    "closed_occurrence_ids",
    "last_reviewed_occurrence_id",
}


class OccurrenceLedgerError(ValueError):
    """Raised when an occurrence packet or cursor is malformed."""


@dataclass(frozen=True)
class Occurrence:
    occurrence_id: str
    stable_key: str
    source_sha256: str
    page: int
    crop_id: str
    fields: Dict[str, str]
    risk: str


@dataclass(frozen=True)
class KeyRecord:
    stable_key: str
    source_sha256: str


@dataclass(frozen=True)
class CandidateRow:
    row_id: str
    stable_key: str
    source_sha256: str
    fields: Dict[str, str]


@dataclass(frozen=True)
class AllowlistEntry:
    stable_key: str
    source_sha256: str
    status: str


@dataclass(frozen=True)
class ResumeCursor:
    packet_id: str
    closed_occurrence_ids: Tuple[str, ...]
    last_reviewed_occurrence_id: Optional[str]
    next_occurrence_id: Optional[str] = None


@dataclass(frozen=True)
class LedgerIssue:
    code: str
    severity: str
    message: str
    stable_key: str = ""
    occurrence_id: str = ""
    row_id: str = ""


@dataclass
class OccurrencePacket:
    packet_id: str
    occurrences: List[Occurrence]
    unique_key_ledger: List[KeyRecord]
    candidate_rows: List[CandidateRow]
    allowlist: List[AllowlistEntry]


@dataclass
class LedgerReceipt:
    generated_utc: str
    packet_id: str
    occurrence_count: int
    unique_keys_from_occurrences: int
    unique_keys_from_ledger: int
    candidate_row_count: int
    allowlist_count: int
    closed_same_hash_skipped: int
    reopen_count: int
    issues: List[LedgerIssue]
    duplicate_occurrence_keys: List[str]
    orphan_candidate_keys: List[str]
    missing_candidate_keys: List[str]
    orphan_ledger_keys: List[str]
    missing_ledger_keys: List[str]
    hash_mismatches: List[str]
    field_conflicts: List[str]
    resume_cursor: Dict[str, object]
    technical_pass: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(default_factory=lambda: [
        "technical_pass is ledger-consistency only; it is not package release",
    ])

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_sha256(value: object, label: str) -> str:
    digest = value.casefold() if isinstance(value, str) else ""
    if not _is_sha256(digest):
        raise OccurrenceLedgerError(f"{label} has an invalid source_sha256")
    return digest


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise OccurrenceLedgerError(f"{label} must be a single-line string")
    return value.strip()


def _require_fields(value: object, label: str) -> Dict[str, str]:
    if not isinstance(value, dict):
        raise OccurrenceLedgerError(f"{label} must be an object")
    fields: Dict[str, str] = {}
    for key, field_value in value.items():
        name = _require_text(key, f"{label} field name")
        if not isinstance(field_value, str):
            raise OccurrenceLedgerError(f"{label}.{name} must be a string")
        if "\n" in field_value:
            raise OccurrenceLedgerError(
                f"{label}.{name} must be a single-line string"
            )
        fields[name] = field_value
    return fields


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OccurrenceLedgerError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise OccurrenceLedgerError(f"{path} must contain a JSON object")
    return payload


def _parse_key_records(
    rows: Sequence[object],
    label: str,
    required_keys: set[str],
) -> List[KeyRecord]:
    records: List[KeyRecord] = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict) or set(raw) != required_keys:
            raise OccurrenceLedgerError(f"{label} {index} has invalid fields")
        digest = _require_sha256(raw["source_sha256"], f"{label} {index}")
        records.append(
            KeyRecord(
                stable_key=_require_text(raw["stable_key"], "stable_key"),
                source_sha256=digest,
            )
        )
    return records


def parse_occurrence_packet(payload: Dict[str, object]) -> OccurrencePacket:
    if set(payload) != REQUIRED_PACKET_KEYS:
        raise OccurrenceLedgerError(
            "Occurrence packet has invalid top-level fields"
        )
    if (
        payload["schema_id"] != PACKET_SCHEMA_ID
        or payload["schema_version"] != PACKET_SCHEMA_VERSION
    ):
        raise OccurrenceLedgerError("Occurrence packet schema is invalid")
    packet_id = _require_text(payload["packet_id"], "packet_id")
    raw_occurrences = payload["occurrences"]
    raw_ledger = payload["unique_key_ledger"]
    raw_rows = payload["candidate_rows"]
    raw_allowlist = payload["allowlist"]
    if not isinstance(raw_occurrences, list) or not raw_occurrences:
        raise OccurrenceLedgerError("occurrences must be a non-empty list")
    if not isinstance(raw_ledger, list) or not raw_ledger:
        raise OccurrenceLedgerError("unique_key_ledger must be a non-empty list")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise OccurrenceLedgerError("candidate_rows must be a non-empty list")
    if not isinstance(raw_allowlist, list):
        raise OccurrenceLedgerError("allowlist must be a list")

    occurrences: List[Occurrence] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_occurrences):
        if not isinstance(raw, dict) or set(raw) != REQUIRED_OCCURRENCE_KEYS:
            raise OccurrenceLedgerError(
                f"occurrence {index} has invalid fields"
            )
        occurrence_id = _require_text(raw["occurrence_id"], "occurrence_id")
        if occurrence_id in seen_ids:
            raise OccurrenceLedgerError(
                f"occurrence_id is duplicated: {occurrence_id}"
            )
        seen_ids.add(occurrence_id)
        digest = _require_sha256(
            raw["source_sha256"],
            f"occurrence {occurrence_id}",
        )
        page = raw["page"]
        if type(page) is not int or page < 1:
            raise OccurrenceLedgerError(
                f"occurrence {occurrence_id} page must be an integer >= 1"
            )
        risk = raw["risk"]
        if risk not in RISK_VALUES:
            raise OccurrenceLedgerError(
                f"occurrence {occurrence_id} has an invalid risk"
            )
        occurrences.append(
            Occurrence(
                occurrence_id=occurrence_id,
                stable_key=_require_text(raw["stable_key"], "stable_key"),
                source_sha256=digest,
                page=page,
                crop_id=_require_text(raw["crop_id"], "crop_id"),
                fields=_require_fields(raw["fields"], "fields"),
                risk=risk,
            )
        )

    ledger = _parse_key_records(
        raw_ledger,
        "unique_key_ledger",
        REQUIRED_KEY_RECORD_KEYS,
    )
    allowlist_records = []
    seen_allowlist: set[str] = set()
    for index, raw in enumerate(raw_allowlist):
        if not isinstance(raw, dict) or set(raw) != REQUIRED_ALLOWLIST_KEYS:
            raise OccurrenceLedgerError(f"allowlist {index} has invalid fields")
        digest = _require_sha256(raw["source_sha256"], f"allowlist {index}")
        stable_key = _require_text(raw["stable_key"], "stable_key")
        if stable_key in seen_allowlist:
            raise OccurrenceLedgerError(
                f"allowlist stable_key is duplicated: {stable_key}"
            )
        seen_allowlist.add(stable_key)
        status = _require_text(raw["status"], "status")
        if status != "source_proved":
            raise OccurrenceLedgerError(
                f"allowlist {stable_key} status must be source_proved"
            )
        allowlist_records.append(
            AllowlistEntry(
                stable_key=stable_key,
                source_sha256=digest,
                status=status,
            )
        )

    rows: List[CandidateRow] = []
    seen_row_ids: set[str] = set()
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, dict) or set(raw) != REQUIRED_ROW_KEYS:
            raise OccurrenceLedgerError(
                f"candidate_rows {index} has invalid fields"
            )
        row_id = _require_text(raw["row_id"], "row_id")
        if row_id in seen_row_ids:
            raise OccurrenceLedgerError(f"row_id is duplicated: {row_id}")
        seen_row_ids.add(row_id)
        digest = _require_sha256(
            raw["source_sha256"],
            f"candidate_rows {row_id}",
        )
        rows.append(
            CandidateRow(
                row_id=row_id,
                stable_key=_require_text(raw["stable_key"], "stable_key"),
                source_sha256=digest,
                fields=_require_fields(raw["fields"], "fields"),
            )
        )
    return OccurrencePacket(
        packet_id=packet_id,
        occurrences=occurrences,
        unique_key_ledger=ledger,
        candidate_rows=rows,
        allowlist=allowlist_records,
    )


def parse_resume_cursor(
    payload: Dict[str, object],
    *,
    expected_packet_id: str,
) -> ResumeCursor:
    if set(payload) != REQUIRED_CURSOR_KEYS:
        raise OccurrenceLedgerError("Resume cursor has invalid top-level fields")
    if (
        payload["schema_id"] != CURSOR_SCHEMA_ID
        or payload["schema_version"] != CURSOR_SCHEMA_VERSION
    ):
        raise OccurrenceLedgerError("Resume cursor schema is invalid")
    packet_id = _require_text(payload["packet_id"], "packet_id")
    if packet_id != expected_packet_id:
        raise OccurrenceLedgerError(
            "Resume cursor packet_id does not match the occurrence packet"
        )
    raw_closed = payload["closed_occurrence_ids"]
    if not isinstance(raw_closed, list):
        raise OccurrenceLedgerError("closed_occurrence_ids must be a list")
    closed: List[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_closed):
        occurrence_id = _require_text(item, f"closed_occurrence_ids[{index}]")
        if occurrence_id in seen:
            raise OccurrenceLedgerError(
                f"closed_occurrence_ids is duplicated: {occurrence_id}"
            )
        seen.add(occurrence_id)
        closed.append(occurrence_id)
    last_reviewed = payload["last_reviewed_occurrence_id"]
    if last_reviewed is not None:
        last_reviewed = _require_text(
            last_reviewed,
            "last_reviewed_occurrence_id",
        )
    return ResumeCursor(
        packet_id=packet_id,
        closed_occurrence_ids=tuple(closed),
        last_reviewed_occurrence_id=last_reviewed,
    )


def _consensus_fields(
    occurrences: Sequence[Occurrence],
    issues: List[LedgerIssue],
) -> Dict[str, str]:
    values: Dict[str, Dict[str, List[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for occurrence in occurrences:
        for name, value in occurrence.fields.items():
            values[name][value].append(occurrence.occurrence_id)
    consensus: Dict[str, str] = {}
    for name, by_value in values.items():
        if len(by_value) != 1:
            issues.append(
                LedgerIssue(
                    code="occurrence_field_conflict",
                    severity="blocking",
                    message=(
                        f"Occurrences of {occurrences[0].stable_key!r} disagree "
                        f"on {name!r}"
                    ),
                    stable_key=occurrences[0].stable_key,
                )
            )
            continue
        consensus[name] = next(iter(by_value))
    return consensus


def _record_missing(
    left: Iterable[str],
    right: Iterable[str],
) -> Tuple[List[str], List[str]]:
    left_set = set(left)
    right_set = set(right)
    return sorted(right_set - left_set), sorted(left_set - right_set)


def _record_unbound_source_hash(
    issues: List[LedgerIssue],
    key: str,
    item_hashes: set[str],
    bound_hashes: set[str],
    message: str,
) -> None:
    if bound_hashes and item_hashes - bound_hashes:
        issues.append(
            LedgerIssue(
                code="source_hash_mismatch",
                severity="blocking",
                message=message,
                stable_key=key,
            )
        )


def compare_packet(
    packet: OccurrencePacket,
    *,
    resume_cursor: Optional[ResumeCursor] = None,
) -> LedgerReceipt:
    issues: List[LedgerIssue] = []
    occurrences_by_key: Dict[str, List[Occurrence]] = defaultdict(list)
    occurrence_hashes: Dict[str, set[str]] = defaultdict(set)
    for occurrence in packet.occurrences:
        occurrences_by_key[occurrence.stable_key].append(occurrence)
        occurrence_hashes[occurrence.stable_key].add(occurrence.source_sha256)

    duplicate_occurrence_keys = sorted(
        key
        for key, group in occurrences_by_key.items()
        if len(group) > 1
    )
    for key, hashes in occurrence_hashes.items():
        if len(hashes) != 1:
            issues.append(
                LedgerIssue(
                    code="source_hash_mismatch",
                    severity="blocking",
                    message=(
                        f"Occurrences of {key!r} bind more than one source hash"
                    ),
                    stable_key=key,
                )
            )

    ledger_by_key: Dict[str, List[KeyRecord]] = defaultdict(list)
    for record in packet.unique_key_ledger:
        ledger_by_key[record.stable_key].append(record)
    for key, records in ledger_by_key.items():
        if len(records) != 1:
            issues.append(
                LedgerIssue(
                    code="duplicate_ledger_key",
                    severity="blocking",
                    message=f"unique_key_ledger repeats {key!r}",
                    stable_key=key,
                )
            )
        _record_unbound_source_hash(
            issues,
            key,
            {record.source_sha256 for record in records},
            occurrence_hashes.get(key, set()),
            f"Ledger hash for {key!r} is not bound to its occurrences",
        )

    rows_by_key: Dict[str, List[CandidateRow]] = defaultdict(list)
    for row in packet.candidate_rows:
        rows_by_key[row.stable_key].append(row)
    for key, rows in rows_by_key.items():
        if len(rows) != 1:
            issues.append(
                LedgerIssue(
                    code="duplicate_candidate_key",
                    severity="blocking",
                    message=f"candidate_rows repeats {key!r}",
                    stable_key=key,
                )
            )
        _record_unbound_source_hash(
            issues,
            key,
            {row.source_sha256 for row in rows},
            occurrence_hashes.get(key, set()),
            f"Candidate hash for {key!r} is not bound to its occurrences",
        )

    allowlist_by_key = {
        entry.stable_key: entry for entry in packet.allowlist
    }
    for key, entry in allowlist_by_key.items():
        occ_hashes = occurrence_hashes.get(key, set())
        if key not in occurrence_hashes:
            issues.append(
                LedgerIssue(
                    code="allowlist_orphan",
                    severity="blocking",
                    message=f"Allowlist key {key!r} is absent from occurrences",
                    stable_key=key,
                )
            )
        elif entry.source_sha256 not in occ_hashes:
            issues.append(
                LedgerIssue(
                    code="allowlist_hash_mismatch",
                    severity="blocking",
                    message=(
                        f"Allowlist hash for {key!r} is not bound to its "
                        "occurrences"
                    ),
                    stable_key=key,
                )
            )

    occurrence_keys = set(occurrences_by_key)
    ledger_keys = set(ledger_by_key)
    candidate_keys = set(rows_by_key)
    orphan_ledger_keys, missing_ledger_keys = _record_missing(
        occurrence_keys,
        ledger_keys,
    )
    orphan_candidate_keys, missing_candidate_keys = _record_missing(
        occurrence_keys,
        candidate_keys,
    )
    if orphan_ledger_keys or missing_ledger_keys:
        issues.append(
            LedgerIssue(
                code="unique_key_count_mismatch",
                severity="blocking",
                message=(
                    "Occurrence unique keys "
                    f"({len(occurrence_keys)}) differ from ledger unique keys "
                    f"({len(ledger_keys)})"
                ),
            )
        )
        for key in orphan_ledger_keys:
            issues.append(
                LedgerIssue(
                    code="orphan_ledger_key",
                    severity="blocking",
                    message=f"Ledger key {key!r} is absent from occurrences",
                    stable_key=key,
                )
            )
        for key in missing_ledger_keys:
            issues.append(
                LedgerIssue(
                    code="missing_ledger_key",
                    severity="blocking",
                    message=f"Occurrence key {key!r} is absent from the ledger",
                    stable_key=key,
                )
            )
    if (
        len(packet.candidate_rows) != len(occurrence_keys)
        or orphan_candidate_keys
        or missing_candidate_keys
    ):
        issues.append(
            LedgerIssue(
                code="candidate_row_count_mismatch",
                severity="blocking",
                message=(
                    "Candidate row count "
                    f"({len(packet.candidate_rows)}) does not match occurrence "
                    f"unique keys ({len(occurrence_keys)}) or ledger unique "
                    f"keys ({len(ledger_keys)})"
                ),
            )
        )
        for key in orphan_candidate_keys:
            issues.append(
                LedgerIssue(
                    code="orphan_candidate_key",
                    severity="blocking",
                    message=f"Candidate key {key!r} is absent from occurrences",
                    stable_key=key,
                )
            )
        for key in missing_candidate_keys:
            issues.append(
                LedgerIssue(
                    code="missing_candidate_key",
                    severity="blocking",
                    message=(
                        f"Occurrence key {key!r} is absent from candidate rows"
                    ),
                    stable_key=key,
                )
            )

    field_conflicts: List[str] = []
    hash_mismatches = sorted(
        {
            issue.stable_key
            for issue in issues
            if issue.code in {
                "source_hash_mismatch",
                "allowlist_hash_mismatch",
            }
            and issue.stable_key
        }
    )
    for key, occurrences in occurrences_by_key.items():
        consensus = _consensus_fields(occurrences, issues)
        rows = rows_by_key.get(key, [])
        if len(rows) != 1:
            continue
        row = rows[0]
        names = sorted(set(consensus) | set(row.fields))
        for name in names:
            if name not in consensus:
                code = "extra_candidate_field"
                message = (
                    f"Candidate {row.row_id} adds {name!r} without "
                    "occurrence support"
                )
            elif name not in row.fields:
                code = "missing_candidate_field"
                message = (
                    f"Candidate {row.row_id} is missing occurrence "
                    f"field {name!r}"
                )
            elif row.fields[name] != consensus[name]:
                code = "field_conflict"
                message = (
                    f"Candidate {row.row_id} {name!r} disagrees with "
                    "occurrence consensus"
                )
            else:
                continue
            issues.append(
                LedgerIssue(
                    code=code,
                    severity="blocking",
                    message=message,
                    stable_key=key,
                    row_id=row.row_id,
                )
            )
            field_conflicts.append(f"{key}:{name}")

    closed_from_cursor = set(
        resume_cursor.closed_occurrence_ids if resume_cursor else ()
    )
    skipped = 0
    reopen: List[Occurrence] = []
    for occurrence in packet.occurrences:
        allowlist = allowlist_by_key.get(occurrence.stable_key)
        same_hash_closed = (
            occurrence.risk == CLOSED_RISK
            and allowlist is not None
            and allowlist.source_sha256 == occurrence.source_sha256
        )
        cursor_closed = occurrence.occurrence_id in closed_from_cursor
        if same_hash_closed or cursor_closed:
            skipped += 1
            continue
        reopen.append(occurrence)
    next_occurrence_id = (
        reopen[0].occurrence_id if reopen else None
    )
    last_reviewed = (
        resume_cursor.last_reviewed_occurrence_id if resume_cursor else None
    )
    cursor_payload = {
        "schema_id": CURSOR_SCHEMA_ID,
        "schema_version": CURSOR_SCHEMA_VERSION,
        "packet_id": packet.packet_id,
        "closed_occurrence_ids": sorted(closed_from_cursor),
        "last_reviewed_occurrence_id": last_reviewed,
        "next_occurrence_id": next_occurrence_id,
    }
    return LedgerReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        packet_id=packet.packet_id,
        occurrence_count=len(packet.occurrences),
        unique_keys_from_occurrences=len(occurrence_keys),
        unique_keys_from_ledger=len(ledger_keys),
        candidate_row_count=len(packet.candidate_rows),
        allowlist_count=len(packet.allowlist),
        closed_same_hash_skipped=skipped,
        reopen_count=len(reopen),
        issues=issues,
        duplicate_occurrence_keys=duplicate_occurrence_keys,
        orphan_candidate_keys=orphan_candidate_keys,
        missing_candidate_keys=missing_candidate_keys,
        orphan_ledger_keys=orphan_ledger_keys,
        missing_ledger_keys=missing_ledger_keys,
        hash_mismatches=hash_mismatches,
        field_conflicts=field_conflicts,
        resume_cursor=cursor_payload,
        technical_pass=not issues,
    )


def write_receipt(receipt: LedgerReceipt, output_path: Path) -> None:
    output_path.write_text(
        json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_resume_cursor(receipt: LedgerReceipt, output_path: Path) -> None:
    payload = dict(receipt.resume_cursor)
    payload.pop("next_occurrence_id", None)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare an isolated occurrence/unique-key/candidate packet "
            "without mutating production."
        )
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume-cursor", type=Path)
    parser.add_argument("--write-resume-cursor", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        packet = parse_occurrence_packet(_load_json(args.packet))
        cursor = None
        if args.resume_cursor is not None:
            cursor = parse_resume_cursor(
                _load_json(args.resume_cursor),
                expected_packet_id=packet.packet_id,
            )
        receipt = compare_packet(packet, resume_cursor=cursor)
        write_receipt(receipt, args.output)
        if args.write_resume_cursor is not None:
            write_resume_cursor(receipt, args.write_resume_cursor)
    except (OSError, OccurrenceLedgerError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "technical_pass": receipt.technical_pass,
                "occurrence_count": receipt.occurrence_count,
                "unique_keys_from_occurrences": (
                    receipt.unique_keys_from_occurrences
                ),
                "unique_keys_from_ledger": receipt.unique_keys_from_ledger,
                "candidate_row_count": receipt.candidate_row_count,
                "closed_same_hash_skipped": receipt.closed_same_hash_skipped,
                "reopen_count": receipt.reopen_count,
                "next_occurrence_id": receipt.resume_cursor[
                    "next_occurrence_id"
                ],
                "issue_count": len(receipt.issues),
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
