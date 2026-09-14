"""Connection probe, occurrence build from crops, and Drive readback."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from horizon.connect_status import probe_connections
from horizon.drive_readback import (
    DriveReadbackError,
    assess_drive_readback,
    is_drive_isolated_copy,
)
from horizon.occurrence_build import build_occurrence_packet
from horizon.occurrence_ledger import compare_packet, parse_occurrence_packet
from horizon.package_finish import run_finish


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _crop_packet() -> dict[str, object]:
    page_hash = _sha("render-1")
    return {
        "schema_id": "dbx.page_render_crop_packet",
        "schema_version": "1.0",
        "packet_id": "SYNTH-OCC-BUILD",
        "expected_page_count": 1,
        "pages": [{"page": 1, "source_sha256": page_hash}],
        "crops": [
            {
                "row_id": "p01r01",
                "page": 1,
                "crop_id": "p01r01",
                "source_sha256": page_hash,
                "docno": "2026-09901",
                "bookpage": "",
                "rec_date": "1/2/2026",
                "doc_date": "",
                "grantor": "SYNTH SURVEYOR",
                "grantee": "The Public",
            }
        ],
    }


def test_connect_status_without_roots_is_blocked_not_complete() -> None:
    receipt = probe_connections()
    assert receipt.packages_complete is False
    assert receipt.technical_pass is False
    assert receipt.connected_root_count == 0
    assert any("cursor worker" in action for action in receipt.next_actions)
    assert any("pc_operator" in action for action in receipt.next_actions)
    assert any("chat/OCR" in action for action in receipt.next_actions)
    assert any("handwritten" in action for action in receipt.next_actions)


def test_connect_status_sees_a_readable_root(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    receipt = probe_connections([f"pc={root}"])
    assert receipt.packages_complete is False
    assert receipt.technical_pass is True
    assert receipt.connected_root_count == 1
    assert receipt.roots[0].readable is True


def test_occurrence_build_from_checkable_crops_compares() -> None:
    packet = build_occurrence_packet(_crop_packet())
    receipt = compare_packet(parse_occurrence_packet(packet))
    assert receipt.technical_pass is True
    assert receipt.occurrence_count == 1
    assert packet["occurrences"][0]["risk"] == "novel"


def test_is_drive_isolated_copy_requires_isolated_dir_and_section_name() -> None:
    assert is_drive_isolated_copy(
        Path("Section 15/Isolated/section15-letter.xlsx"), 15
    )
    assert is_drive_isolated_copy(
        Path("Section 13/Isolated/section13-delta-2.xlsx"), 13
    )
    assert not is_drive_isolated_copy(
        Path("Section 15/section15-letter.xlsx"), 15
    )
    assert not is_drive_isolated_copy(Path("receipts/drive-copy.xlsx"), 15)
    assert not is_drive_isolated_copy(
        Path("Section 13/Isolated/section15-letter.xlsx"), 13
    )
    assert not is_drive_isolated_copy(
        Path("Section 15/Isolated/section15-letter.xlsx"), 13
    )


def test_drive_readback_requires_distinct_identical_copy(tmp_path: Path) -> None:
    workbook = tmp_path / "isolated.xlsx"
    copy = tmp_path / "drive.xlsx"
    other = tmp_path / "other.xlsx"
    workbook.write_bytes(b"SYNTH-WORKBOOK")
    copy.write_bytes(b"SYNTH-WORKBOOK")
    other.write_bytes(b"SYNTH-OTHER")
    ok = assess_drive_readback(workbook, copy)
    assert ok.technical_pass is True
    bad = assess_drive_readback(workbook, other)
    assert bad.technical_pass is False
    with pytest.raises(DriveReadbackError, match="distinct"):
        assess_drive_readback(workbook, workbook)


def test_finish_runner_connect_and_readback_never_complete(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    receipt = run_finish(
        sections=[15],
        roots=[f"pc={root}"],
        connect_status=True,
    )
    assert receipt.packages_complete is False
    names = {gate.name for gate in receipt.gates}
    assert "connect_status" in names
    assert "source_acquisition" in names
    packet = tmp_path / "crops.json"
    packet.write_text(json.dumps(_crop_packet()), encoding="utf-8")
    built = run_finish(sections=[11], page_render_packet=packet)
    assert built.packages_complete is False
    assert {gate.name for gate in built.gates} >= {
        "page_render_export",
        "reextraction",
        "occurrence_ledger",
    }
    assert all(gate.technical_pass for gate in built.gates)
