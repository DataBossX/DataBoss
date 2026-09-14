"""Examiner fill queue lists remaining blanks; it does not invent values."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pytest

from horizon.examiner_queue import build_examiner_queue, proposed_deltas_from_queue
from horizon.isolated_delta import IsolatedDeltaError, parse_delta_packet, write_delta_draft
from horizon.index_export import export_index_packet
from horizon.pc_operator import build_work_order


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
    path.parent.mkdir(parents=True, exist_ok=True)
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
    workbook.save(path)
    workbook.close()


def test_one_source_blank_stays_unfilled(tmp_path: Path) -> None:
    master = tmp_path / "master.xlsx"
    pdf = tmp_path / "pdf.xlsx"
    hand = tmp_path / "hand.xlsx"
    candidate = tmp_path / "working.xlsx"
    _write_index(master, legal="ONLY MASTER LEGAL")
    _write_index(pdf, legal="")
    _write_index(hand, legal="")
    _write_index(candidate, legal="")
    packet = export_index_packet(
        "SECTION15-INDEX",
        master=master,
        pdf_index=pdf,
        handwritten=hand,
        candidate=candidate,
    )
    queue = build_examiner_queue(packet, candidate, packet_id="SECTION15-QUEUE")
    assert queue["schema_id"] == "dbx.examiner_fill_queue"
    legal = next(item for item in queue["items"] if item["field"] == "legal_description")
    assert legal["action"] == "source_proved_fill"
    assert legal["proposed_value"] == ""
    assert legal["candidate_value"] == ""
    assert legal["confidence"] == "low"


def test_operator_writes_examiner_queue(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    section = root / "Section 15"
    _write_index(section / "Master Abstract.xlsx", legal="ONLY MASTER LEGAL")
    _write_index(section / "County Index.xlsx", legal="")
    _write_index(section / "Handwritten Index.xlsx", legal="")
    _write_index(section / "Working Abstract.xlsx", legal="")
    (section / "Recorded Faces").mkdir(parents=True)
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(
        b"%PDF-1.1\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj\n"
        b"trailer<< /Root 1 0 R >>\n"
    )
    receipts = tmp_path / "private-receipts"
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    queue_path = receipts / "section15-examiner-queue.json"
    assert queue_path.is_file()
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    legal = next(item for item in queue["items"] if item["field"] == "legal_description")
    assert legal["proposed_value"] == ""
    assert any("blank required field" in hold for hold in receipt.sections[0].holds)
    assert any(
        "isolated_delta" in command for command in receipt.sections[0].next_commands
    )
    assert not (receipts / "section15-delta-draft.json").is_file()


def test_two_source_blank_writes_unapproved_delta_draft(tmp_path: Path) -> None:
    master = tmp_path / "master.xlsx"
    pdf = tmp_path / "pdf.xlsx"
    hand = tmp_path / "hand.xlsx"
    candidate = tmp_path / "working.xlsx"
    _write_index(master, legal="SYNTH AGREED LEGAL")
    _write_index(pdf, legal="SYNTH AGREED LEGAL")
    _write_index(hand, legal="")
    _write_index(candidate, legal="")
    packet = export_index_packet(
        "SECTION15-INDEX",
        master=master,
        pdf_index=pdf,
        handwritten=hand,
        candidate=candidate,
    )
    queue = build_examiner_queue(packet, candidate, packet_id="SECTION15-QUEUE")
    legal = next(item for item in queue["items"] if item["field"] == "legal_description")
    assert legal["action"] == "proposed_delta_pending"
    assert legal["proposed_value"] == "SYNTH AGREED LEGAL"
    deltas = proposed_deltas_from_queue(queue)
    assert len(deltas) == 1
    assert deltas[0]["field"] == "legal_description"
    assert deltas[0]["value"] == "SYNTH AGREED LEGAL"
    assert deltas[0]["replace"] is False
    draft = write_delta_draft(
        workbook=candidate,
        deltas=deltas,
        output=tmp_path / "draft.json",
        packet_id="SECTION15-DELTA",
    )
    assert draft["status"] == "UNAPPROVED_DRAFT"
    with pytest.raises(IsolatedDeltaError, match="invalid top-level"):
        parse_delta_packet(draft)


def test_operator_writes_delta_draft_when_letter_skips_repair(tmp_path: Path) -> None:
    import shutil

    root = tmp_path / "pc-root"
    section = root / "Section 15"
    _write_index(section / "Master Abstract.xlsx", legal="SYNTH AGREED LEGAL")
    _write_index(section / "County Index.xlsx", legal="SYNTH AGREED LEGAL")
    _write_index(section / "Handwritten Index.xlsx", legal="")
    _write_index(section / "Working Abstract.xlsx", legal="")
    (section / "Recorded Faces").mkdir(parents=True)
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(
        b"%PDF-1.1\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj\n"
        b"trailer<< /Root 1 0 R >>\n"
    )
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    shutil.copy2(section / "Working Abstract.xlsx", receipts / "section15-letter.xlsx")
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    draft_path = receipts / "section15-delta-draft.json"
    assert draft_path.is_file()
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    assert draft["schema_id"] == "dbx.source_proved_delta_draft"
    assert draft["status"] == "UNAPPROVED_DRAFT"
    assert draft["deltas"][0]["value"] == "SYNTH AGREED LEGAL"
    attest = next(
        command
        for command in receipt.sections[0].next_commands
        if "horizon.isolated_delta" in command and "--attest" in command
    )
    assert str(draft_path) in attest
    assert "EXAMINER_NAME" in attest
