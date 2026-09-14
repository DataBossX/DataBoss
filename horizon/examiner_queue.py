"""Build an examiner fill queue from remaining index blanks and conflicts.

The queue does not invent legal, party, recorded-date, or document-type
values. One-source blanks stay blank. Conflicts stay unresolved until a
writer-held isolated delta supplies source-proved text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .index_export import IndexExportError, export_faces, refresh_candidate
from .index_reconciliation import (
    FieldScore,
    IndexReconciliationError,
    reconcile_indexes,
)
from .isolated_delta import ALLOWED_FIELDS, REQUIRED_DELTA_KEYS, sha256_file

QUEUE_SCHEMA_ID = "dbx.examiner_fill_queue"
QUEUE_SCHEMA_VERSION = "1.0"


class ExaminerQueueError(ValueError):
    """Raised when an examiner fill queue cannot be built safely."""


def queue_from_scores(
    scores: Sequence[FieldScore],
    *,
    packet_id: str,
    workbook_sha256: str,
) -> Dict[str, object]:
    token = packet_id.strip()
    digest = workbook_sha256.casefold()
    if not token or "\n" in token:
        raise ExaminerQueueError("packet_id must be a single-line string")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ExaminerQueueError("workbook_sha256 is invalid")
    items: List[Dict[str, object]] = []
    for score in scores:
        if score.confidence == "conflict":
            action = "resolve_conflict"
        elif score.eligible_for_isolated_delta and not score.candidate_value:
            action = "proposed_delta_pending"
        elif not score.candidate_value:
            action = "source_proved_fill"
        else:
            continue
        items.append(
            {
                "row_key": score.stable_key,
                "field": score.field,
                "candidate_value": score.candidate_value,
                "confidence": score.confidence,
                "agreeing_sources": list(score.agreeing_sources),
                "conflict_values": dict(score.conflict_values),
                "provenance": list(score.provenance),
                "proposed_value": (
                    score.consensus_value if score.eligible_for_isolated_delta else ""
                ),
                "action": action,
            }
        )
    return {
        "schema_id": QUEUE_SCHEMA_ID,
        "schema_version": QUEUE_SCHEMA_VERSION,
        "packet_id": token,
        "workbook_sha256": digest,
        "items": items,
        "blank_count": sum(1 for item in items if item["action"] != "resolve_conflict"),
        "conflict_count": sum(
            1 for item in items if item["action"] == "resolve_conflict"
        ),
        "notes": [
            "This queue does not invent legal, party, or date values",
            "One-source blanks require a writer-held source-proved fill",
            "Put only source-proved text in sectionN-deltas.json",
        ],
    }


def proposed_deltas_from_queue(queue: Dict[str, object]) -> List[Dict[str, object]]:
    """Collect medium/high agreed fills. One-source and conflicts stay out."""
    if not isinstance(queue, dict) or queue.get("schema_id") != QUEUE_SCHEMA_ID:
        raise ExaminerQueueError("examiner fill queue schema is invalid")
    items = queue.get("items")
    if not isinstance(items, list):
        raise ExaminerQueueError("examiner fill queue items must be a list")
    deltas: List[Dict[str, object]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ExaminerQueueError(f"items[{index}] must be an object")
        if item.get("action") != "proposed_delta_pending":
            continue
        proposed = item.get("proposed_value")
        field_name = item.get("field")
        if not isinstance(proposed, str) or not proposed.strip():
            continue
        if field_name not in ALLOWED_FIELDS:
            raise ExaminerQueueError(f"items[{index}] field is not allowed")
        provenance = item.get("provenance")
        if not isinstance(provenance, list) or not provenance:
            raise ExaminerQueueError(
                f"items[{index}] proposed fill is missing provenance"
            )
        first = provenance[0]
        if not isinstance(first, dict):
            raise ExaminerQueueError(f"items[{index}] provenance[0] is invalid")
        page = first.get("page")
        if type(page) is not int or page < 1:
            raise ExaminerQueueError(f"items[{index}] provenance page is invalid")
        delta = {
            "row_key": item.get("row_key"),
            "field": field_name,
            "value": proposed,
            "source_sha256": first.get("source_sha256"),
            "page": page,
            "crop_id": first.get("crop_id"),
            "replace": False,
        }
        if set(delta) != REQUIRED_DELTA_KEYS:
            raise ExaminerQueueError(f"items[{index}] could not build a delta")
        deltas.append(delta)
    return deltas


def onesource_rows_from_queue(queue: Dict[str, object]) -> List[Dict[str, object]]:
    """Build empty-value rows for one-source blanks and conflicts.

    Horizon does not copy a single source's text into ``value``.
    """
    if not isinstance(queue, dict) or queue.get("schema_id") != QUEUE_SCHEMA_ID:
        raise ExaminerQueueError("examiner fill queue schema is invalid")
    items = queue.get("items")
    if not isinstance(items, list):
        raise ExaminerQueueError("examiner fill queue items must be a list")
    rows: List[Dict[str, object]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ExaminerQueueError(f"items[{index}] must be an object")
        if item.get("action") not in {"source_proved_fill", "resolve_conflict"}:
            continue
        field_name = item.get("field")
        if field_name not in ALLOWED_FIELDS:
            raise ExaminerQueueError(f"items[{index}] field is not allowed")
        provenance = item.get("provenance")
        if not isinstance(provenance, list) or not provenance:
            continue
        first = provenance[0]
        if not isinstance(first, dict):
            raise ExaminerQueueError(f"items[{index}] provenance[0] is invalid")
        page = first.get("page")
        if type(page) is not int or page < 1:
            raise ExaminerQueueError(f"items[{index}] provenance page is invalid")
        source_values = []
        for entry in provenance:
            if not isinstance(entry, dict):
                continue
            value = entry.get("value")
            if isinstance(value, str) and value.strip():
                source_values.append(
                    {
                        "source": entry.get("source"),
                        "value": value,
                        "source_sha256": entry.get("source_sha256"),
                    }
                )
        rows.append(
            {
                "row_key": item.get("row_key"),
                "field": field_name,
                "value": "",
                "source_sha256": first.get("source_sha256"),
                "page": page,
                "crop_id": first.get("crop_id"),
                "replace": False,
                "action": item.get("action"),
                "source_values": source_values,
                "conflict_values": dict(item.get("conflict_values") or {}),
            }
        )
    return rows


def build_examiner_queue(
    index_packet: Dict[str, object],
    workbook: Path,
    *,
    packet_id: str,
) -> Dict[str, object]:
    workbook = workbook.expanduser().resolve()
    if not workbook.is_file():
        raise ExaminerQueueError(f"workbook does not exist: {workbook}")
    try:
        faces = export_faces(workbook)
        refreshed = refresh_candidate(index_packet, faces)
        recon = reconcile_indexes(refreshed)
    except (OSError, IndexExportError, IndexReconciliationError) as exc:
        raise ExaminerQueueError(str(exc)) from exc
    return queue_from_scores(
        recon.field_scores,
        packet_id=packet_id,
        workbook_sha256=sha256_file(workbook),
    )


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExaminerQueueError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExaminerQueueError(f"{path} must contain a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "List remaining index blanks and conflicts for writer-held fills. "
            "Does not invent field values."
        )
    )
    parser.add_argument("--index-packet", type=Path, required=True)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--packet-id", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        queue = build_examiner_queue(
            _load_json(args.index_packet),
            args.workbook,
            packet_id=args.packet_id,
        )
        args.output.write_text(
            json.dumps(queue, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (OSError, ExaminerQueueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "blank_count": queue["blank_count"],
                "conflict_count": queue["conflict_count"],
                "packages_complete": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
