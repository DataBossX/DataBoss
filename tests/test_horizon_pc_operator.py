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


def _minimal_pdf() -> bytes:
    return (
        b"%PDF-1.1\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj\n"
        b"trailer<< /Root 1 0 R >>\n"
    )


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
    (faces / "Instrument 1.pdf").write_bytes(_minimal_pdf())


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
    assert any("page_render_export" in command for command in by_section[11].next_commands)
    assert any("pdf_census" in command for command in by_section[13].next_commands)
    assert any("--inventory" in command for command in by_section[13].next_commands)
    assert "horizon.native_print" in joined
    assert "--attest" in joined
    assert "--from-draft" in joined
    assert "horizon.human_release" in joined
    assert "owner-review-draft.json" in joined
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
    assert (receipts / "section15-workbook-export.json").is_file()
    assert (receipts / "section15-workbook-occurrence.json").is_file()
    draft = json.loads(
        (receipts / "section15-native-print-draft.json").read_text(encoding="utf-8")
    )
    assert draft["schema_id"] == "dbx.native_print_draft"
    assert draft["status"] == "UNAPPROVED_DRAFT"
    letter_sha = __import__(
        "horizon.isolated_delta", fromlist=["sha256_file"]
    ).sha256_file(letter)
    assert draft["workbook_sha256"] == letter_sha
    release_draft = json.loads(
        (receipts / "section15-owner-review-draft.json").read_text(encoding="utf-8")
    )
    assert release_draft["schema_id"] == "dbx.human_release_draft"
    assert release_draft["status"] == "UNAPPROVED_DRAFT"
    assert release_draft["workbook_sha256"] == letter_sha
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


def test_execute_publishes_isolated_workbook_to_drive(tmp_path: Path) -> None:
    pc = tmp_path / "pc-root"
    drive = tmp_path / "drive-root"
    pc.mkdir()
    _section15_tree(pc)
    _section15_tree(drive)
    receipts = tmp_path / "private-receipts"
    receipt = build_work_order(
        roots=[f"pc={pc}", f"drive={drive}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    letter = receipts / "section15-letter.xlsx"
    published = drive / "Section 15" / "Isolated" / "section15-letter.xlsx"
    assert letter.is_file()
    assert published.is_file()
    assert published.read_bytes() == letter.read_bytes()
    finish = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    drive_gate = next(
        gate for gate in finish["gates"] if gate["name"] == "drive_readback"
    )
    assert drive_gate["technical_pass"] is True
    published.write_bytes(b"different-drive-bytes")
    second = build_work_order(
        roots=[f"pc={pc}", f"drive={drive}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    assert published.read_bytes() == b"different-drive-bytes"
    assert any(
        "different hash" in hold for hold in second.sections[0].holds
    )


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
    census_packet = receipts / "section15-pdf-census-packet.json"
    assert census_packet.is_file()
    census_payload = json.loads(census_packet.read_text(encoding="utf-8"))
    assert census_payload["files"][0]["expected_pages"] == 1
    census_gate = next(
        gate for gate in finish["gates"] if gate["name"] == "pdf_census"
    )
    assert census_gate["technical_pass"] is True
    assert census_gate["detail"]["empty_text_files"] == 1


def test_operator_drops_stale_native_print_after_delta(tmp_path: Path) -> None:
    from horizon.isolated_delta import sha256_file, write_delta_packet
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
    write_delta_packet(
        workbook=letter,
        deltas=[
            {
                "row_key": "2026-09901|",
                "field": "comments",
                "value": "SYNTH SOURCE NOTE",
                "source_sha256": "a" * 64,
                "page": 1,
                "crop_id": "note",
                "replace": False,
            }
        ],
        output=receipts / "section15-delta-packet.json",
        packet_id="SYNTH-P15-DELTA",
    )
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    assert (receipts / "section15-delta.xlsx").is_file()
    native = next(
        command
        for command in second.sections[0].next_commands
        if "horizon.native_print" in command
    )
    assert "--attest" in native
    assert str(receipts / "section15-delta.xlsx") in native
    assert "section15-letter.xlsx" not in native
    assert any(
        "different workbook hash" in hold for hold in second.sections[0].holds
    )
    finish = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    assert all(gate["name"] != "native_print" for gate in finish["gates"])
    draft = json.loads(
        (receipts / "section15-native-print-draft.json").read_text(encoding="utf-8")
    )
    assert draft["workbook_sha256"] == sha256_file(receipts / "section15-delta.xlsx")


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


def test_operator_discovers_and_applies_delta_packet(tmp_path: Path) -> None:
    from horizon.isolated_delta import write_delta_packet

    root = tmp_path / "pc-root"
    section = root / "Section 13"
    section.mkdir(parents=True)
    _write_penterra(section / "Master Abstract.xlsx")
    _write_penterra(section / "County Index.xlsx")
    _write_penterra(section / "Handwritten Index.xlsx")
    (section / "Recorded Faces").mkdir()
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(b"%PDF-1.1 face")
    receipts = tmp_path / "private-receipts"
    first = build_work_order(
        roots=[f"pc={root}"],
        sections=[13],
        receipt_dir=receipts,
        execute=True,
    )
    assert first.packages_complete is False
    letter = receipts / "section13-letter.xlsx"
    write_delta_packet(
        workbook=letter,
        deltas=[
            {
                "row_key": "2026-09901|",
                "field": "comments",
                "value": "SYNTH SOURCE NOTE",
                "source_sha256": "a" * 64,
                "page": 1,
                "crop_id": "note",
                "replace": False,
            }
        ],
        output=receipts / "section13-delta-packet.json",
        packet_id="SYNTH-P13-DELTA",
    )
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[13],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    assert second.sections[0].execute_error == ""
    assert (receipts / "section13-delta.xlsx").is_file()
    finish = json.loads(
        (receipts / "section13-finish.json").read_text(encoding="utf-8")
    )
    delta = next(gate for gate in finish["gates"] if gate["name"] == "isolated_delta")
    assert delta["technical_pass"] is True
    native = next(
        command
        for command in second.sections[0].next_commands
        if "horizon.native_print" in command
    )
    release = next(
        command
        for command in second.sections[0].next_commands
        if "horizon.human_release" in command
    )
    assert str(receipts / "section13-delta.xlsx") in native
    assert "section13-letter.xlsx" not in native
    assert str(receipts / "section13-delta.xlsx") in release
    assert "section13-letter.xlsx" not in release


def test_operator_chains_a_second_delta_onto_current_isolated(
    tmp_path: Path,
) -> None:
    from horizon.isolated_delta import attest_delta_draft, write_delta_packet

    root = tmp_path / "pc-root"
    section = root / "Section 15"
    _write_penterra(section / "Master Abstract.xlsx")
    _write_penterra(section / "County Index.xlsx")
    _write_penterra(section / "Handwritten Index.xlsx")
    _write_penterra(section / "Working Abstract.xlsx")
    (section / "Recorded Faces").mkdir()
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(b"%PDF-1.1 face")
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    import shutil

    shutil.copy2(section / "Working Abstract.xlsx", receipts / "section15-letter.xlsx")
    first = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert first.packages_complete is False
    letter = receipts / "section15-letter.xlsx"
    write_delta_packet(
        workbook=letter,
        deltas=[
            {
                "row_key": "2026-09901|",
                "field": "comments",
                "value": "SYNTH SOURCE NOTE",
                "source_sha256": "a" * 64,
                "page": 1,
                "crop_id": "note",
                "replace": False,
            }
        ],
        output=receipts / "section15-delta-packet.json",
        packet_id="SYNTH-P15-DELTA-1",
    )
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    first_delta = receipts / "section15-delta.xlsx"
    assert first_delta.is_file()
    assert list(receipts.glob("section15-delta-packet-applied-*.json"))
    assert not (receipts / "section15-delta-packet.json").is_file()
    draft = receipts / "section15-delta-draft.json"
    if draft.is_file():
        attest_delta_draft(
            json.loads(draft.read_text(encoding="utf-8")),
            workbook=first_delta,
            output=receipts / "section15-delta-packet.json",
            operator="Pat Examiner",
        )
    else:
        write_delta_packet(
            workbook=first_delta,
            deltas=[
                {
                    "row_key": "2026-09901|",
                    "field": "comments",
                    "value": "SYNTH SECOND NOTE",
                    "source_sha256": "b" * 64,
                    "page": 1,
                    "crop_id": "note2",
                    "replace": True,
                }
            ],
            output=receipts / "section15-delta-packet.json",
            packet_id="SYNTH-P15-DELTA-2",
        )
    third = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert third.packages_complete is False
    chained = receipts / "section15-delta-2.xlsx"
    assert chained.is_file()
    native = next(
        command
        for command in third.sections[0].next_commands
        if "horizon.native_print" in command
    )
    assert str(chained) in native
    assert "section15-letter.xlsx" not in native
    assert "section15-delta.xlsx" not in native


def test_operator_hashes_phase2_snapshot_renders_for_section11(
    tmp_path: Path,
) -> None:
    from horizon.authority_promote import promote
    from horizon.isolated_delta import sha256_file

    root = tmp_path / "pc-root"
    section = root / "Section 11"
    _write_penterra(section / "Master Abstract.xlsx")
    _write_penterra(section / "County Index.xlsx")
    _write_penterra(section / "Handwritten Index.xlsx")
    faces = section / "Recorded Faces"
    faces.mkdir(parents=True)
    render = faces / "page-01.png"
    render.write_bytes(b"SYNTH-P11-RENDER")
    receipts = tmp_path / "private-receipts"
    first = build_work_order(
        roots=[f"pc={root}"],
        sections=[11],
        receipt_dir=receipts,
        execute=True,
    )
    assert first.packages_complete is False
    phase1_draft = json.loads(
        (receipts / "section11-crops-draft.json").read_text(encoding="utf-8")
    )
    assert phase1_draft["pages"] == []
    assert first.authority_promote_command is not None
    promote(
        draft_path=Path(first.authority_draft_path),
        output=receipts / "source-authority.json",
        project_manifest_output=receipts / "project_manifest.json",
        project_id="DBX-TEST",
        decision_id="SOURCE-AUTH-011",
        approved_by="Pat Examiner",
        confirm_sections=[11],
        roots=[f"pc={root}"],
    )
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[11],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    draft = json.loads(
        (receipts / "section11-crops-draft.json").read_text(encoding="utf-8")
    )
    assert draft["status"] == "UNAPPROVED_DRAFT"
    assert draft["expected_page_count"] == 1
    assert draft["crops"] == []
    assert draft["pages"][0]["path"].endswith("Recorded Faces/page-01.png")
    snap_render = (
        receipts
        / "intake-snapshot"
        / "section11"
        / "pc"
        / "Section 11"
        / "Recorded Faces"
        / "page-01.png"
    )
    assert draft["pages"][0]["source_sha256"] == sha256_file(snap_render)
    joined = "\n".join(second.sections[0].next_commands)
    assert str(receipts / "intake-snapshot" / "section11") in joined


def test_operator_writes_section11_crops_draft_from_renders(tmp_path: Path) -> None:
    from horizon.isolated_delta import sha256_file

    root = tmp_path / "pc-root"
    (root / "Section 11").mkdir(parents=True)
    receipts = tmp_path / "private-receipts"
    renders = receipts / "section11-renders"
    renders.mkdir(parents=True)
    page = renders / "page-01.png"
    page.write_bytes(b"SYNTH-RENDER")
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[11],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    draft_path = receipts / "section11-crops-draft.json"
    assert draft_path.is_file()
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    assert draft["schema_id"] == "dbx.page_render_crop_draft"
    assert draft["status"] == "UNAPPROVED_DRAFT"
    assert draft["expected_page_count"] == 1
    assert draft["crops"] == []
    assert draft["pages"][0]["source_sha256"] == sha256_file(page)
    joined = "\n".join(receipt.sections[0].next_commands)
    assert "horizon.page_render_export" in joined
    assert str(renders.resolve()) in joined
    assert "14" not in draft["notes"][0]


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


def test_execute_inventories_section_pdfs_and_binds_census(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    section = root / "Section 13"
    section.mkdir(parents=True)
    _write_penterra(section / "Master Abstract.xlsx")
    _write_penterra(section / "County Index.xlsx")
    _write_penterra(section / "Handwritten Index.xlsx")
    (section / "Recorded Faces").mkdir()
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(b"%PDF-1.1 face")
    receipts = tmp_path / "private-receipts"
    pdfs = receipts / "section13-pdfs"
    pdfs.mkdir(parents=True)
    (pdfs / "part4.pdf").write_bytes(
        b"%PDF-1.1\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj\n"
        b"trailer<< /Root 1 0 R >>\n"
    )
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[13],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    packet_path = receipts / "section13-pdf-census-packet.json"
    assert packet_path.is_file()
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert packet["files"][0]["expected_pages"] == 1
    assert packet["files"][0]["expected_pages"] != 462
    finish = json.loads(
        (receipts / "section13-finish.json").read_text(encoding="utf-8")
    )
    census = next(gate for gate in finish["gates"] if gate["name"] == "pdf_census")
    assert census["technical_pass"] is True
    assert census["detail"]["empty_text_files"] == 1
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[13],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    assert all(
        "pdf_census --inventory" not in command
        and "--inventory" not in command
        for command in second.sections[0].next_commands
    )


def test_cli_writes_receipt_and_stays_incomplete(tmp_path: Path) -> None:
    output = tmp_path / "operator.json"
    result = main(["--output", str(output), "--section", "15"])
    assert result == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["packages_complete"] is False
    assert payload["acquisition_phase"] == "blocked"
    assert payload["schema_id"] == "dbx.pc_operator_receipt"
