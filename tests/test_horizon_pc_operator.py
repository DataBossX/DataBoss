"""PC operator emits Phase 1 work orders and never completes packages."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl

from horizon.pc_operator import build_work_order, main


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


def _write_penterra(path: Path) -> None:
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
            "SYNTH TRACT 15-45N-76W",
            "",
        ]
    )
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_LETTER
    sheet.print_title_rows = "1:8"
    workbook.save(path)
    workbook.close()


def _section15_tree(root: Path) -> None:
    section = root / "Section 15"
    _write_penterra(section / "Master Abstract.xlsx")
    _write_penterra(section / "County Index.xlsx")
    _write_penterra(section / "Handwritten Index.xlsx")
    _write_penterra(section / "Working Abstract.xlsx")
    faces = section / "Recorded Faces"
    faces.mkdir(parents=True, exist_ok=True)
    (faces / "Instrument 1.pdf").write_bytes(b"%PDF-1.1 synth face")


def test_operator_without_roots_is_blocked_and_incomplete() -> None:
    receipt = build_work_order()
    assert receipt.packages_complete is False
    assert receipt.technical_pass is False
    assert receipt.acquisition_phase == "blocked"
    assert receipt.requested_sections == [15, 13, 11]
    assert all(order.file_count == 0 for order in receipt.sections)
    assert any("pc_operator" in action for action in receipt.next_actions)


def test_operator_phase1_emits_section_commands(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    receipts = tmp_path / "private-receipts"
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15, 13, 11],
        receipt_dir=receipts,
    )
    assert receipt.packages_complete is False
    assert receipt.technical_pass is True
    assert receipt.acquisition_phase == "phase1_inventory"
    by_section = {order.section: order for order in receipt.sections}
    section15 = by_section[15]
    assert section15.ready_for_extraction is False
    assert section15.missing_required_roles == [
        "source_document",
        "master_workbook",
        "index",
    ]
    assert section15.missing_candidate_roles == []
    assert section15.file_count >= 4
    slots = {pick.slot: pick for pick in section15.candidate_picks}
    assert slots["master"].exportable is True
    assert slots["pdf_index"].exportable is True
    assert slots["handwritten"].exportable is True
    assert slots["candidate"].relative_path.endswith("Working Abstract.xlsx")
    joined = "\n".join(section15.next_commands)
    assert "horizon.index_export" in joined
    assert "horizon.package_finish" in joined
    assert "--master" in joined
    assert "--pdf-index" in joined
    assert "--handwritten" in joined
    assert str(receipts / "section15-index-packet.json") in joined
    assert by_section[13].ready_for_extraction is False
    assert "master_workbook" in by_section[13].missing_candidate_roles
    assert by_section[11].ready_for_extraction is False
    assert any("page-render" in command for command in by_section[11].next_commands)
    assert any("Phase 2" in action for action in receipt.next_actions)


def test_pdf_index_is_not_treated_as_exportable(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    section = root / "Section 13"
    section.mkdir(parents=True)
    _write_penterra(section / "Master Abstract.xlsx")
    (section / "County Index.pdf").write_bytes(b"%PDF-1.1 synth index")
    (section / "Recorded Faces").mkdir()
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(b"%PDF-1.1 face")
    receipt = build_work_order(roots=[f"pc={root}"], sections=[13])
    assert receipt.packages_complete is False
    order = receipt.sections[0]
    pdf_pick = next(pick for pick in order.candidate_picks if pick.slot == "pdf_index")
    assert pdf_pick.exportable is False
    joined = "\n".join(order.next_commands)
    assert "--pdf-index" not in joined
    assert "--master" in joined


def test_cli_writes_receipt_and_stays_incomplete(tmp_path: Path) -> None:
    output = tmp_path / "operator.json"
    result = main(["--output", str(output), "--section", "15"])
    assert result == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["packages_complete"] is False
    assert payload["acquisition_phase"] == "blocked"
    assert payload["schema_id"] == "dbx.pc_operator_receipt"
