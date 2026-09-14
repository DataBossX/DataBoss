"""Synthetic tests for occurrence / unique-key / candidate ledger comparison."""

import hashlib
import json
from pathlib import Path

from horizon.occurrence_ledger import (
    OccurrenceLedgerError,
    compare_packet,
    main,
    parse_occurrence_packet,
    parse_resume_cursor,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _occurrence(
    occurrence_id: str,
    stable_key: str,
    *,
    source: str = "face-a",
    page: int = 1,
    crop_id: str | None = None,
    fields: dict[str, str] | None = None,
    risk: str = "novel",
) -> dict[str, object]:
    return {
        "occurrence_id": occurrence_id,
        "stable_key": stable_key,
        "source_sha256": _sha(source),
        "page": page,
        "crop_id": crop_id or f"{occurrence_id}-crop",
        "fields": fields
        or {
            "party": f"{stable_key} PARTY",
            "date_role": "recorded",
            "legal": f"{stable_key} TRACT",
        },
        "risk": risk,
    }


def _key(stable_key: str, source: str = "face-a") -> dict[str, str]:
    return {"stable_key": stable_key, "source_sha256": _sha(source)}


def _row(
    row_id: str,
    stable_key: str,
    *,
    source: str = "face-a",
    fields: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "row_id": row_id,
        "stable_key": stable_key,
        "source_sha256": _sha(source),
        "fields": fields
        or {
            "party": f"{stable_key} PARTY",
            "date_role": "recorded",
            "legal": f"{stable_key} TRACT",
        },
    }


def _allow(
    stable_key: str,
    source: str = "face-a",
) -> dict[str, str]:
    return {
        "stable_key": stable_key,
        "source_sha256": _sha(source),
        "status": "source_proved",
    }


def _packet(
    *,
    packet_id: str = "SYNTH-OCC-001",
    occurrences: list[dict[str, object]],
    ledger: list[dict[str, str]],
    rows: list[dict[str, object]],
    allowlist: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "schema_id": "dbx.occurrence_packet",
        "schema_version": "1.0",
        "packet_id": packet_id,
        "occurrences": occurrences,
        "unique_key_ledger": ledger,
        "candidate_rows": rows,
        "allowlist": allowlist or [],
    }


def _clean_packet() -> dict[str, object]:
    keys = ["SYNTH-KEY-A", "SYNTH-KEY-B", "SYNTH-KEY-C", "SYNTH-KEY-D"]
    return _packet(
        occurrences=[
            _occurrence(
                f"occ-{index + 1:03d}",
                key,
                risk="closed_same_hash" if index < 2 else "high_risk",
            )
            for index, key in enumerate(keys)
        ],
        ledger=[_key(key) for key in keys],
        rows=[_row(f"R6-{index + 1:03d}", key) for index, key in enumerate(keys)],
        allowlist=[_allow("SYNTH-KEY-A"), _allow("SYNTH-KEY-B")],
    )


def test_consistent_packet_passes_and_skips_closed_same_hash() -> None:
    receipt = compare_packet(parse_occurrence_packet(_clean_packet()))

    assert receipt.technical_pass
    assert receipt.occurrence_count == 4
    assert receipt.unique_keys_from_occurrences == 4
    assert receipt.unique_keys_from_ledger == 4
    assert receipt.candidate_row_count == 4
    assert receipt.allowlist_count == 2
    assert receipt.closed_same_hash_skipped == 2
    assert receipt.reopen_count == 2
    assert receipt.resume_cursor["next_occurrence_id"] == "occ-003"
    assert receipt.notes[0].startswith("technical_pass is ledger-consistency")


def test_p11_shaped_count_contradiction_is_blocking() -> None:
    # 8 raw occurrences, 6 unique from occurrences, 7 ledger keys, 5 rows.
    occurrence_keys = [
        "SYNTH-KEY-A",
        "SYNTH-KEY-A",
        "SYNTH-KEY-B",
        "SYNTH-KEY-C",
        "SYNTH-KEY-C",
        "SYNTH-KEY-D",
        "SYNTH-KEY-E",
        "SYNTH-KEY-F",
    ]
    ledger_keys = [
        "SYNTH-KEY-A",
        "SYNTH-KEY-B",
        "SYNTH-KEY-C",
        "SYNTH-KEY-D",
        "SYNTH-KEY-E",
        "SYNTH-KEY-F",
        "SYNTH-KEY-G",
    ]
    row_keys = [
        "SYNTH-KEY-A",
        "SYNTH-KEY-B",
        "SYNTH-KEY-C",
        "SYNTH-KEY-D",
        "SYNTH-KEY-E",
    ]
    payload = _packet(
        packet_id="SYNTH-P11-SHAPE",
        occurrences=[
            _occurrence(
                f"occ-{index + 1:03d}",
                key,
                page=1 + index,
                risk="closed_same_hash" if key in {"SYNTH-KEY-A", "SYNTH-KEY-B", "SYNTH-KEY-C"} else "disputed",
            )
            for index, key in enumerate(occurrence_keys)
        ],
        ledger=[_key(key) for key in ledger_keys],
        rows=[_row(f"R6-{index + 1:03d}", key) for index, key in enumerate(row_keys)],
        allowlist=[
            _allow("SYNTH-KEY-A"),
            _allow("SYNTH-KEY-B"),
            _allow("SYNTH-KEY-C"),
        ],
    )
    receipt = compare_packet(parse_occurrence_packet(payload))

    assert not receipt.technical_pass
    assert receipt.occurrence_count == 8
    assert receipt.unique_keys_from_occurrences == 6
    assert receipt.unique_keys_from_ledger == 7
    assert receipt.candidate_row_count == 5
    assert receipt.allowlist_count == 3
    assert receipt.closed_same_hash_skipped == 5
    assert receipt.duplicate_occurrence_keys == ["SYNTH-KEY-A", "SYNTH-KEY-C"]
    assert receipt.orphan_ledger_keys == ["SYNTH-KEY-G"]
    assert receipt.missing_candidate_keys == ["SYNTH-KEY-F"]
    codes = {issue.code for issue in receipt.issues}
    assert "unique_key_count_mismatch" in codes
    assert "candidate_row_count_mismatch" in codes
    assert "orphan_ledger_key" in codes
    assert "missing_candidate_key" in codes


def test_duplicate_orphan_hash_and_field_conflicts() -> None:
    payload = _packet(
        occurrences=[
            _occurrence("occ-001", "SYNTH-KEY-A", fields={"party": "ALPHA LLC"}),
            _occurrence(
                "occ-002",
                "SYNTH-KEY-A",
                fields={"party": "ALPHA HW"},
            ),
            _occurrence("occ-003", "SYNTH-KEY-B"),
        ],
        ledger=[
            _key("SYNTH-KEY-A"),
            _key("SYNTH-KEY-A", source="other-face"),
            _key("SYNTH-KEY-B"),
        ],
        rows=[
            _row("R6-001", "SYNTH-KEY-A", fields={"party": "ALPHA LLC"}),
            _row("R6-002", "SYNTH-KEY-B", source="other-face"),
            _row("R6-003", "SYNTH-KEY-Z"),
        ],
        allowlist=[_allow("SYNTH-KEY-B", source="wrong-face")],
    )
    receipt = compare_packet(parse_occurrence_packet(payload))

    assert not receipt.technical_pass
    codes = {issue.code for issue in receipt.issues}
    assert "occurrence_field_conflict" in codes
    assert "duplicate_ledger_key" in codes
    assert "source_hash_mismatch" in codes
    assert "allowlist_hash_mismatch" in codes
    assert "orphan_candidate_key" in codes
    assert "SYNTH-KEY-Z" in receipt.orphan_candidate_keys


def test_extra_candidate_field_is_rejected() -> None:
    payload = _clean_packet()
    payload["candidate_rows"][3]["fields"]["invented"] = "not from source"
    receipt = compare_packet(parse_occurrence_packet(payload))

    assert not receipt.technical_pass
    assert any(issue.code == "extra_candidate_field" for issue in receipt.issues)
    assert "SYNTH-KEY-D:invented" in receipt.field_conflicts


def test_resume_cursor_skips_closed_ids_without_hiding_counts(
    tmp_path: Path,
) -> None:
    payload = _clean_packet()
    packet = parse_occurrence_packet(payload)
    cursor = parse_resume_cursor(
        {
            "schema_id": "dbx.occurrence_resume_cursor",
            "schema_version": "1.0",
            "packet_id": "SYNTH-OCC-001",
            "closed_occurrence_ids": ["occ-003"],
            "last_reviewed_occurrence_id": "occ-003",
        },
        expected_packet_id="SYNTH-OCC-001",
    )
    receipt = compare_packet(packet, resume_cursor=cursor)

    assert receipt.technical_pass
    assert receipt.closed_same_hash_skipped == 3
    assert receipt.reopen_count == 1
    assert receipt.resume_cursor["next_occurrence_id"] == "occ-004"
    assert receipt.occurrence_count == 4


def test_unknown_packet_fields_fail_closed() -> None:
    payload = _clean_packet()
    payload["comment"] = "ignore me"
    try:
        parse_occurrence_packet(payload)
    except OccurrenceLedgerError as exc:
        assert "top-level" in str(exc)
    else:
        raise AssertionError("expected unknown fields to fail")


def test_cli_writes_receipt_and_cursor(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(_clean_packet()), encoding="utf-8")
    output = tmp_path / "receipt.json"
    cursor_out = tmp_path / "cursor.json"

    result = main(
        [
            "--packet",
            str(packet_path),
            "--output",
            str(output),
            "--write-resume-cursor",
            str(cursor_out),
        ]
    )

    assert result == 0
    receipt = json.loads(output.read_text(encoding="utf-8"))
    cursor = json.loads(cursor_out.read_text(encoding="utf-8"))
    assert receipt["technical_pass"] is True
    assert receipt["schema_id"] == "dbx.occurrence_ledger_receipt"
    assert cursor["schema_id"] == "dbx.occurrence_resume_cursor"
    assert cursor["packet_id"] == "SYNTH-OCC-001"
    assert "next_occurrence_id" not in cursor


def test_cli_reports_blocked_packet(tmp_path: Path) -> None:
    payload = _clean_packet()
    payload["unique_key_ledger"].append(_key("SYNTH-KEY-Z"))
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "receipt.json"

    result = main(["--packet", str(packet_path), "--output", str(output)])

    assert result == 2
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["technical_pass"] is False
    assert receipt["unique_keys_from_ledger"] == 5
