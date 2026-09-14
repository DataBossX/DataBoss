"""PC operator emits Phase 1 work orders and never completes packages."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pytest

from horizon.pc_operator import FinishBindings, PcOperatorError, build_work_order, main


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
    assert "horizon.native_print" in joined
    assert "--write" in joined
    assert "horizon.human_release" in joined
    assert any("Phase 2" in action for action in receipt.next_actions)
    draft_path = receipts / "authority-draft.json"
    assert draft_path.is_file()
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    assert draft["schema_id"] == "dbx.source_authority_draft"
    assert draft["status"] == "UNAPPROVED_DRAFT"
    assert draft["approved_by"] == ""
    assert receipt.authority_draft_path == str(draft_path.resolve())
    assert receipt.schema_version == "1.3"
    assert receipt.authority_promote_command is not None
    assert "horizon.authority_promote" in receipt.authority_promote_command
    assert "EXAMINER_NAME" in receipt.authority_promote_command
    assert "--confirm-section 15" in receipt.authority_promote_command
    roles = {item["role"] for item in draft["authorities"] if item["section"] == 15}
    assert roles == {"source_document", "master_workbook", "index"}
    assert any("UNAPPROVED_DRAFT" in action for action in receipt.next_actions)
    bound = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        bindings=FinishBindings(
            authority_manifest=tmp_path / "authority.json",
            project_manifest=tmp_path / "project.json",
        ),
    )
    joined_bound = "\n".join(bound.sections[0].next_commands)
    assert "--authority-manifest" in joined_bound
    assert "--project-manifest" in joined_bound
    assert "--snapshot-directory" in joined_bound


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


def test_execute_runs_isolated_recon_without_completing(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    receipts = tmp_path / "private-receipts"
    source = root / "Section 15" / "Working Abstract.xlsx"
    before = source.read_bytes()
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    assert receipt.technical_pass is True
    order = receipt.sections[0]
    assert order.executed is True
    assert order.execute_error == ""
    assert order.finish_packages_complete is False
    packet = receipts / "section15-index-packet.json"
    finish = receipts / "section15-finish.json"
    letter = receipts / "section15-letter.xlsx"
    assert packet.is_file()
    assert finish.is_file()
    assert letter.is_file()
    payload = json.loads(finish.read_text(encoding="utf-8"))
    assert payload["packages_complete"] is False
    assert source.read_bytes() == before
    assert any("Executed isolated" in action for action in receipt.next_actions)
    assert (receipts / "authority-draft.json").is_file()
    assert receipt.authority_draft["status"] == "UNAPPROVED_DRAFT"
    letter = receipts / "section15-letter.xlsx"
    copy = receipts / "drive-copy.xlsx"
    copy.write_bytes(letter.read_bytes())
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    finish = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    drive_gate = next(
        gate for gate in finish["gates"] if gate["name"] == "drive_readback"
    )
    assert drive_gate["technical_pass"] is True


def test_operator_discovers_promoted_authority_for_phase2(tmp_path: Path) -> None:
    from horizon.authority_promote import promote

    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    receipts = tmp_path / "private-receipts"
    first = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert first.packages_complete is False
    assert first.authority_promote_command is not None
    promote(
        draft_path=Path(first.authority_draft_path),
        output=receipts / "source-authority.json",
        project_manifest_output=receipts / "project_manifest.json",
        project_id="DBX-TEST",
        decision_id="SOURCE-AUTH-001",
        approved_by="Pat Examiner",
        confirm_sections=[15],
        roots=[f"pc={root}"],
    )
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    assert second.authority_promote_command is None
    finish = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    acquisition = next(
        gate for gate in finish["gates"] if gate["name"] == "source_acquisition"
    )
    assert acquisition["technical_pass"] is True
    assert acquisition["detail"]["phase"] == "phase2_snapshot"
    assert (receipts / "intake-snapshot" / "section15").is_dir()
    assert (receipts / "section15-acquisition.json").is_file()
    live_master = root / "Section 15" / "Master Abstract.xlsx"
    live_master.write_bytes(b"changed-after-phase2")
    third = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert third.packages_complete is False
    assert third.sections[0].execute_error == ""
    finish = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    acquisition = next(
        gate for gate in finish["gates"] if gate["name"] == "source_acquisition"
    )
    assert acquisition["technical_pass"] is True
    assert acquisition["detail"]["reused_snapshot"] is True
    snap_master = (
        receipts
        / "intake-snapshot"
        / "section15"
        / "pc"
        / "Section 15"
        / "Master Abstract.xlsx"
    )
    assert snap_master.read_bytes() != b"changed-after-phase2"


def test_operator_discovers_receipt_dir_native_print(tmp_path: Path) -> None:
    from horizon.native_print import write_native_print_packet

    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    receipts = tmp_path / "private-receipts"
    first = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert first.packages_complete is False
    letter = receipts / "section15-letter.xlsx"
    write_native_print_packet(
        workbook=letter,
        output=receipts / "section15-native-print.json",
        operator="Pat Examiner",
        page_count=1,
        expected_page_count=1,
        packet_id="SECTION15-PRINT",
    )
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    assert all(
        "horizon.native_print" not in command
        for command in second.sections[0].next_commands
    )
    finish = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    native = next(gate for gate in finish["gates"] if gate["name"] == "native_print")
    assert native["technical_pass"] is True


def test_execute_refuses_repo_receipt_dir_and_requires_private_dir() -> None:
    repo_horizon = Path(__file__).resolve().parents[1] / "horizon"
    with pytest.raises(PcOperatorError, match="outside this repository"):
        build_work_order(execute=True, receipt_dir=repo_horizon)
    with pytest.raises(PcOperatorError, match="outside this repository"):
        build_work_order(receipt_dir=repo_horizon)
    with pytest.raises(PcOperatorError, match="receipt-dir"):
        build_work_order(execute=True)


def test_execute_discovers_page_render_packet_for_section_11(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    section = root / "Section 11"
    section.mkdir(parents=True)
    packet = {
        "schema_id": "dbx.page_render_crop_packet",
        "schema_version": "1.0",
        "packet_id": "SYNTH-P11-CROPS",
        "expected_page_count": 1,
        "pages": [
            {
                "page": 1,
                "source_sha256": "a" * 64,
            }
        ],
        "crops": [
            {
                "row_id": "p01r01",
                "page": 1,
                "crop_id": "p01r01",
                "source_sha256": "a" * 64,
                "docno": "2026-09901",
                "bookpage": "",
                "rec_date": "1/2/2026",
                "doc_date": "",
                "grantor": "SYNTH SURVEYOR",
                "grantee": "The Public",
            }
        ],
    }
    (section / "page-render-crops.json").write_text(
        json.dumps(packet),
        encoding="utf-8",
    )
    receipts = tmp_path / "private-receipts"
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[11],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    order = receipt.sections[0]
    assert order.executed is True
    assert order.execute_error == ""
    finish = json.loads(
        (receipts / "section11-finish.json").read_text(encoding="utf-8")
    )
    names = {gate["name"] for gate in finish["gates"]}
    assert "page_render_export" in names
    assert "reextraction" in names
    assert "occurrence_ledger" in names


def test_cli_writes_receipt_and_stays_incomplete(tmp_path: Path) -> None:
    output = tmp_path / "operator.json"
    result = main(["--output", str(output), "--section", "15"])
    assert result == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["packages_complete"] is False
    assert payload["acquisition_phase"] == "blocked"
    assert payload["schema_id"] == "dbx.pc_operator_receipt"
