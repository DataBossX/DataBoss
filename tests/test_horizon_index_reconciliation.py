"""Master / PDF / handwritten index reconciliation with field confidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from horizon.index_reconciliation import (
    IndexReconciliationError,
    main,
    reconcile_indexes,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _fields(**overrides: str) -> dict[str, str]:
    payload = {
        "document_type": "Mineral Deed",
        "grantor": "SYNTH ALPHA LLC",
        "grantee": "SYNTH BETA LLC",
        "recorded_date": "1/2/2026",
        "legal_description": "SYNTH TRACT 15-45N-76W",
    }
    payload.update(overrides)
    return payload


def _face(
    key: str,
    source: str,
    *,
    page: int = 1,
    fields: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "stable_key": key,
        "source_sha256": _sha(source),
        "page": page,
        "crop_id": f"{source}-crop",
        "fields": fields or _fields(),
    }


def _packet(**overrides: object) -> dict[str, object]:
    key = "2026-09901|"
    packet = {
        "schema_id": "dbx.index_reconciliation_packet",
        "schema_version": "1.0",
        "packet_id": "SYNTH-RECON-001",
        "master": [_face(key, "master")],
        "pdf_index": [_face(key, "pdf")],
        "handwritten_index": [_face(key, "hand")],
        "candidate_rows": [_face(key, "candidate")],
        "expected_counts": {
            "master": 1,
            "pdf_index": 1,
            "handwritten_index": 1,
            "candidate_rows": 1,
        },
        "orphan_allowlist": [],
    }
    packet.update(overrides)
    return packet


def test_three_way_match_is_high_confidence_and_already_present() -> None:
    receipt = reconcile_indexes(_packet())
    assert receipt.issues == []
    assert receipt.technical_pass is True
    assert receipt.conflict_count == 0
    assert receipt.proposed_deltas == []
    legal = next(
        score
        for score in receipt.field_scores
        if score.field == "legal_description"
    )
    assert legal.confidence == "high"
    assert legal.status == "already_present"
    assert legal.eligible_for_isolated_delta is False


def test_two_sources_agree_on_blank_candidate_emits_proposal() -> None:
    key = "2026-09901|"
    receipt = reconcile_indexes(
        _packet(
            handwritten_index=[],
            candidate_rows=[_face(key, "candidate", fields=_fields(legal_description=""))],
            expected_counts={
                "master": 1,
                "pdf_index": 1,
                "handwritten_index": 0,
                "candidate_rows": 1,
            },
            orphan_allowlist=[
                {
                    "stable_key": key,
                    "present_in": ["master", "pdf_index"],
                    "source_sha256": _sha("master"),
                }
            ],
        )
    )
    assert receipt.technical_pass is True
    assert len(receipt.proposed_deltas) == 1
    proposal = receipt.proposed_deltas[0]
    assert proposal["field"] == "legal_description"
    assert proposal["value"] == "SYNTH TRACT 15-45N-76W"
    assert proposal["confidence"] == "medium"
    assert proposal["replace"] is False
    assert sorted(proposal["agreeing_sources"]) == ["master", "pdf_index"]


def test_conflicting_legals_block_and_do_not_propose() -> None:
    key = "2026-09901|"
    receipt = reconcile_indexes(
        _packet(
            pdf_index=[
                _face(key, "pdf", fields=_fields(legal_description="SYNTH OTHER TRACT"))
            ]
        )
    )
    assert receipt.technical_pass is False
    assert receipt.conflict_count == 1
    assert receipt.proposed_deltas == []
    assert any("conflict" in issue for issue in receipt.issues)


def test_single_source_blank_is_low_confidence_not_a_delta() -> None:
    key = "2026-09901|"
    receipt = reconcile_indexes(
        _packet(
            pdf_index=[],
            handwritten_index=[],
            candidate_rows=[_face(key, "candidate", fields=_fields(legal_description=""))],
            expected_counts={
                "master": 1,
                "pdf_index": 0,
                "handwritten_index": 0,
                "candidate_rows": 1,
            },
            orphan_allowlist=[
                {
                    "stable_key": key,
                    "present_in": ["master"],
                    "source_sha256": _sha("master"),
                }
            ],
        )
    )
    assert receipt.technical_pass is True
    assert receipt.proposed_deltas == []
    assert receipt.low_confidence_blank_count == 1
    legal = next(
        score
        for score in receipt.field_scores
        if score.field == "legal_description"
    )
    assert legal.confidence == "low"
    assert legal.eligible_for_isolated_delta is False


def test_count_mismatch_and_unexpected_orphan_fail(tmp_path: Path) -> None:
    with pytest.raises(IndexReconciliationError, match="duplicate"):
        reconcile_indexes(
            _packet(
                master=[
                    _face("2026-09901|", "master"),
                    _face("2026-09901|", "master-dup"),
                ]
            )
        )
    receipt = reconcile_indexes(
        _packet(
            expected_counts={
                "master": 2,
                "pdf_index": 1,
                "handwritten_index": 1,
                "candidate_rows": 1,
            }
        )
    )
    assert receipt.technical_pass is False
    assert any("count mismatch master" in issue for issue in receipt.issues)

    orphan = reconcile_indexes(
        _packet(
            handwritten_index=[],
            expected_counts={
                "master": 1,
                "pdf_index": 1,
                "handwritten_index": 0,
                "candidate_rows": 1,
            },
        )
    )
    assert orphan.technical_pass is False
    assert any("orphan key" in issue for issue in orphan.issues)

    output = tmp_path / "recon.json"
    result = main(
        [
            "--packet",
            str(tmp_path / "missing.json"),
            "--output",
            str(output),
        ]
    )
    assert result == 1
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps(_packet()), encoding="utf-8")
    result = main(["--packet", str(packet), "--output", str(output)])
    assert result == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["technical_pass"] is True
    assert payload["schema_id"] == "dbx.index_reconciliation_receipt"


def test_candidate_only_key_is_refused() -> None:
    receipt = reconcile_indexes(
        _packet(
            candidate_rows=[
                _face("2026-09901|", "candidate"),
                _face("2026-09999|", "ghost"),
            ],
            expected_counts={
                "master": 1,
                "pdf_index": 1,
                "handwritten_index": 1,
                "candidate_rows": 2,
            },
        )
    )
    assert receipt.technical_pass is False
    assert any("not present in master" in issue for issue in receipt.issues)
