"""Three-workbook index packet export does not invent faces."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pytest

from horizon.index_export import (
    IndexExportError,
    export_index_packet,
    load_orphan_allowlist,
    main,
)
from horizon.index_reconciliation import reconcile_indexes


PENTERRA_HEADERS = [
    "Document Type",
    "Grantor",
    "Grantee",
    "Doc No",
    "Book-Page",
    "Date of Doc",
    "Rec Date",
    "Legal Description",
    "Comments",
]


def _write_index(path: Path, *, legal: str = "SYNTH TRACT 15-45N-76W") -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Index"
    for _ in range(7):
        sheet.append(["SYNTH"])
    sheet.append(PENTERRA_HEADERS)
    sheet.append(
        [
            "Mineral Deed",
            "SYNTH ALPHA LLC",
            "SYNTH BETA LLC",
            "2026-09901",
            "",
            "1/1/2026",
            "1/2/2026",
            legal,
            "",
        ]
    )
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_LETTER
    sheet.print_title_rows = "1:8"
    workbook.save(path)
    workbook.close()


def test_export_index_packet_from_three_workbooks(tmp_path: Path) -> None:
    master = tmp_path / "master.xlsx"
    pdf = tmp_path / "pdf.xlsx"
    hand = tmp_path / "hand.xlsx"
    candidate = tmp_path / "candidate.xlsx"
    _write_index(master)
    _write_index(pdf)
    _write_index(hand)
    _write_index(candidate, legal="")
    packet = export_index_packet(
        "SYNTH-INDEX-PACKET",
        master=master,
        pdf_index=pdf,
        handwritten=hand,
        candidate=candidate,
    )
    assert packet["schema_id"] == "dbx.index_reconciliation_packet"
    assert packet["expected_counts"] == {
        "master": 1,
        "pdf_index": 1,
        "handwritten_index": 1,
        "candidate_rows": 1,
    }
    receipt = reconcile_indexes(packet)
    assert receipt.technical_pass is True
    assert len(receipt.proposed_deltas) == 1
    assert receipt.proposed_deltas[0]["field"] == "legal_description"
    assert receipt.proposed_deltas[0]["confidence"] == "high"


def test_export_index_packet_refuses_no_sources(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.xlsx"
    _write_index(candidate)
    with pytest.raises(IndexExportError, match="master"):
        export_index_packet("SYNTH-EMPTY", candidate=candidate)


def test_cli_writes_packet_and_keeps_single_workbook_faces(tmp_path: Path) -> None:
    master = tmp_path / "master.xlsx"
    pdf = tmp_path / "pdf.xlsx"
    _write_index(master)
    _write_index(pdf)
    packet_path = tmp_path / "packet.json"
    result = main(
        [
            "--packet-id",
            "SYNTH-CLI-PACKET",
            "--master",
            str(master),
            "--pdf-index",
            str(pdf),
            "--workbook",
            str(master),
            "--output",
            str(packet_path),
        ]
    )
    assert result == 0
    payload = json.loads(packet_path.read_text(encoding="utf-8"))
    assert payload["schema_id"] == "dbx.index_reconciliation_packet"
    assert payload["expected_counts"]["candidate_rows"] == 1
    faces = tmp_path / "faces.json"
    result = main(
        [
            "--workbook",
            str(master),
            "--packet-id",
            "SYNTH-FACES",
            "--output",
            str(faces),
        ]
    )
    assert result == 0
    dumped = json.loads(faces.read_text(encoding="utf-8"))
    assert len(dumped["faces"]) == 1
    assert dumped["source_name"] == "candidate_rows"
    missing = main(
        ["--packet-id", "SYNTH-NONE", "--output", str(tmp_path / "none.json")]
    )
    assert missing == 1


def test_orphan_allowlist_loader(tmp_path: Path) -> None:
    allow = tmp_path / "allow.json"
    allow.write_text(
        json.dumps(
            {
                "orphan_allowlist": [
                    {
                        "stable_key": "2026-09901|",
                        "present_in": ["master", "pdf_index"],
                        "source_sha256": "a" * 64,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    loaded = load_orphan_allowlist(allow)
    assert loaded[0]["stable_key"] == "2026-09901|"
    with pytest.raises(IndexExportError, match="list"):
        load_orphan_allowlist(tmp_path / "missing.json")
