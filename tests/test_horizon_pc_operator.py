"""PC operator emits Phase 1 work orders and never completes packages."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pytest

from horizon.isolated_delta import sha256_file
from types import SimpleNamespace

from horizon.drive_readback import is_drive_isolated_copy
from horizon.pc_operator import (
    FinishBindings,
    PcOperatorError,
    _crop_packet_matches_renders,
    _bind_dir_for_section,
    _discover_receipt_dir_packets,
    _drive_section_dir,
    _publish_isolated_to_drive,
    _receipt_packages_complete,
    _same_hash_readback,
    _section_census_packet,
    _section_crop_packet,
    _section_named_packet,
    _section_commands,
    _section_folder_dest,
    build_work_order,
    main,
)


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


def _write_penterra(path: Path, *, legal: str = "SYNTH TRACT 15-45N-76W") -> None:
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
        "handwritten_index",
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
    assert roles == {
        "source_document",
        "master_workbook",
        "index",
        "handwritten_index",
    }
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


def test_operator_remaining_plan_names_classified_roles_as_phase2(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    receipts = tmp_path / "private-receipts"
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    plan = json.loads(
        (receipts / "section15-remaining-plan.json").read_text(encoding="utf-8")
    )
    assert plan["schema_version"] == "1.5"
    assert plan["unauthorized_classified_roles"] == [
        "source_document",
        "master_workbook",
        "index",
        "handwritten_index",
    ]
    assert plan["missing_candidate_roles"] == []
    assert (
        "required role index is classified but not Phase-2 authorized"
        in plan["missing"]
    )
    assert (
        "required role handwritten_index is classified but not Phase-2 authorized"
        in plan["missing"]
    )
    assert "missing required role index" not in plan["missing"]
    assert "missing required role handwritten_index" not in plan["missing"]
    assert any("authority_promote" in item for item in plan["missing"])
    assert plan["next_commands"][0].startswith(
        "Promote classified files with horizon.authority_promote "
        "--confirm-section 15"
    )


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


def test_receipt_packages_complete_requires_remaining_plan() -> None:
    order = SimpleNamespace(section=15, finish_packages_complete=True)
    assert _receipt_packages_complete([order], []) is False
    assert (
        _receipt_packages_complete(
            [order], [{"section": 15, "packages_complete": True}]
        )
        is True
    )
    assert (
        _receipt_packages_complete(
            [order], [{"section": 15, "packages_complete": False}]
        )
        is False
    )
    assert (
        _receipt_packages_complete(
            [order], [{"section": 13, "packages_complete": True}]
        )
        is False
    )
    assert _receipt_packages_complete([], []) is False


def test_next_commands_fill_before_print_and_release(tmp_path: Path) -> None:
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    (receipts / "section15-delta-draft.json").write_text("{}", encoding="utf-8")
    (receipts / "section15-onesource-template.json").write_text(
        "{}", encoding="utf-8"
    )
    commands = _section_commands(
        15,
        root_args=["pc=/tmp"],
        picks=[],
        receipt_dir=str(receipts),
        missing_roles=[],
        bindings=FinishBindings(),
    )

    def first(needle: str) -> int:
        return next(index for index, item in enumerate(commands) if needle in item)

    assert first("horizon.isolated_delta") < first("horizon.native_print")
    assert first("horizon.native_print") < first("horizon.human_release")
    commands11 = _section_commands(
        11,
        root_args=["pc=/tmp"],
        picks=[],
        receipt_dir=str(receipts),
        missing_roles=[],
        bindings=FinishBindings(),
    )
    crops = next(
        index
        for index, item in enumerate(commands11)
        if "horizon.page_render_export" in item
    )
    native = next(
        index
        for index, item in enumerate(commands11)
        if "horizon.native_print" in item
    )
    assert crops < native
    assert any(
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/" in item
        for item in commands
    )
    assert any(
        "Print Preview section15-letter.xlsx on Windows Excel" in item
        for item in commands
    )
    assert any(
        "Attest owner-review of section15-letter.xlsx" in item
        for item in commands
    )


def test_next_commands_name_current_isolated_drive_copy(tmp_path: Path) -> None:
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    (receipts / "section13-delta-2.xlsx").write_bytes(b"SYNTH-DELTA-2")
    commands = _section_commands(
        13,
        root_args=["pc=/tmp"],
        picks=[],
        receipt_dir=str(receipts),
        missing_roles=[],
        bindings=FinishBindings(),
    )
    assert any(
        "Copy section13-delta-2.xlsx into Drive Section 13/Isolated/" in item
        for item in commands
    )
    receipt_bound = _section_commands(
        13,
        root_args=["pc=/tmp"],
        picks=[],
        receipt_dir=str(receipts),
        missing_roles=[],
        bindings=FinishBindings(drive_readback=tmp_path / "drive-copy.xlsx"),
    )
    assert any(
        "Copy section13-delta-2.xlsx into Drive Section 13/Isolated/" in item
        for item in receipt_bound
    )
    isolated = tmp_path / "Section 13" / "Isolated" / "section13-delta-2.xlsx"
    isolated.parent.mkdir(parents=True)
    isolated.write_bytes(b"SYNTH-DELTA-2")
    drive_bound = _section_commands(
        13,
        root_args=["pc=/tmp"],
        picks=[],
        receipt_dir=str(receipts),
        missing_roles=[],
        bindings=FinishBindings(drive_readback=isolated),
    )
    assert not any(
        "Copy section13-delta-2.xlsx into Drive Section 13/Isolated/" in item
        for item in drive_bound
    )
    isolated.write_bytes(b"STALE-ISOLATED-COPY")
    stale_bound = _section_commands(
        13,
        root_args=["pc=/tmp"],
        picks=[],
        receipt_dir=str(receipts),
        missing_roles=[],
        bindings=FinishBindings(drive_readback=isolated),
    )
    assert any(
        "Copy section13-delta-2.xlsx into Drive Section 13/Isolated/" in item
        for item in stale_bound
    )


def test_execute_lists_remaining_work_before_reexport(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    receipts = tmp_path / "private-receipts"
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False

    def first(commands: list[str], needle: str) -> int:
        return next(index for index, item in enumerate(commands) if needle in item)

    commands = receipt.sections[0].next_commands
    assert first(commands, "horizon.native_print") < first(
        commands, "horizon.index_export"
    )
    assert first(commands, "horizon.human_release") < first(
        commands, "horizon.package_finish"
    )
    finish_cmd = next(
        command for command in commands if "horizon.package_finish" in command
    )
    assert str(receipts / "section15-letter.xlsx") in finish_cmd
    plan = json.loads(
        (receipts / "section15-remaining-plan.json").read_text(encoding="utf-8")
    )
    plan_cmds = plan["next_commands"]
    assert first(plan_cmds, "horizon.native_print") < first(
        plan_cmds, "horizon.index_export"
    )
    assert plan["isolated_workbook"]["name"] == "section15-letter.xlsx"
    assert "Print Preview section15-letter.xlsx on Windows Excel" in plan["missing"]
    assert (
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/"
        in plan["missing"]
    )
    assert "Attest owner-review of section15-letter.xlsx" in plan["missing"]
    assert any(
        "Print Preview section15-letter.xlsx on Windows Excel" in item
        for item in commands
    )
    assert any(
        "Attest owner-review of section15-letter.xlsx" in item
        for item in commands
    )


def test_first_execute_keeps_letter_after_print_layout(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    section = root / "Section 15"
    _write_penterra(section / "Master Abstract.xlsx")
    _write_penterra(section / "County Index.xlsx")
    _write_penterra(section / "Handwritten Index.xlsx")
    working = section / "Working Abstract.xlsx"
    _write_penterra(working, legal="")
    loaded = openpyxl.load_workbook(working)
    sheet = loaded["Index"]
    sheet.page_setup.orientation = "portrait"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.print_title_rows = None
    loaded.save(working)
    loaded.close()
    (section / "Recorded Faces").mkdir(parents=True)
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(_minimal_pdf())
    receipts = tmp_path / "private-receipts"
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    letter = receipts / "section15-letter.xlsx"
    assert letter.is_file()
    assert not (receipts / "section15-delta.xlsx").is_file()
    isolated = openpyxl.load_workbook(letter, data_only=True)
    sheet = isolated["Index"]
    assert sheet["H9"].value == "SYNTH TRACT 15-45N-76W"
    assert sheet.page_setup.orientation == "landscape"
    assert int(sheet.page_setup.paperSize) == 1
    assert str(sheet.print_title_rows).replace("$", "") == "1:8"
    isolated.close()
    draft = json.loads(
        (receipts / "section15-native-print-draft.json").read_text(encoding="utf-8")
    )
    letter_sha = __import__(
        "horizon.isolated_delta", fromlist=["sha256_file"]
    ).sha256_file(letter)
    assert draft["workbook_sha256"] == letter_sha
    finish_cmd = next(
        command
        for command in receipt.sections[0].next_commands
        if "horizon.package_finish" in command
    )
    assert str(letter) in finish_cmd
    assert "Working Abstract.xlsx" not in finish_cmd
    assert "--print-layout-output" not in finish_cmd
    payload = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    names = [gate["name"] for gate in payload["gates"]]
    assert "repair_loop" not in names
    recon = next(
        gate for gate in payload["gates"] if gate["name"] == "index_reconciliation"
    )
    assert recon["technical_pass"] is True
    assert recon["detail"]["blank_required_count"] == 0
    assert recon["detail"]["candidate_from"] == "workbook"


def test_existing_a4_letter_is_repaired_in_place(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    letter = receipts / "section15-letter.xlsx"
    _write_penterra(letter)
    loaded = openpyxl.load_workbook(letter)
    sheet = loaded["Index"]
    sheet.page_setup.orientation = "portrait"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.print_title_rows = None
    loaded.save(letter)
    loaded.close()
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    repaired = openpyxl.load_workbook(letter, data_only=True)
    assert repaired["Index"]["H9"].value == "SYNTH TRACT 15-45N-76W"
    assert repaired["Index"].page_setup.orientation == "landscape"
    assert int(repaired["Index"].page_setup.paperSize) == 1
    assert str(repaired["Index"].print_title_rows).replace("$", "") == "1:8"
    repaired.close()
    draft = json.loads(
        (receipts / "section15-native-print-draft.json").read_text(encoding="utf-8")
    )
    letter_sha = __import__(
        "horizon.isolated_delta", fromlist=["sha256_file"]
    ).sha256_file(letter)
    assert draft["workbook_sha256"] == letter_sha


def test_reuse_letter_reruns_agreed_repairs_onto_next_isolated(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pc-root"
    section = root / "Section 15"
    _write_penterra(section / "Master Abstract.xlsx")
    _write_penterra(section / "County Index.xlsx")
    _write_penterra(section / "Handwritten Index.xlsx")
    _write_penterra(section / "Working Abstract.xlsx", legal="")
    faces = section / "Recorded Faces"
    faces.mkdir(parents=True, exist_ok=True)
    (faces / "Instrument 1.pdf").write_bytes(_minimal_pdf())
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    letter = receipts / "section15-letter.xlsx"
    _write_penterra(letter, legal="")
    loaded = openpyxl.load_workbook(letter)
    sheet = loaded["Index"]
    sheet.page_setup.orientation = "portrait"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.print_title_rows = None
    loaded.save(letter)
    loaded.close()
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    isolated = receipts / "section15-delta.xlsx"
    assert isolated.is_file()
    repaired = openpyxl.load_workbook(isolated, data_only=True)
    assert repaired["Index"]["H9"].value == "SYNTH TRACT 15-45N-76W"
    assert repaired["Index"].page_setup.orientation == "landscape"
    assert int(repaired["Index"].page_setup.paperSize) == 1
    assert str(repaired["Index"].print_title_rows).replace("$", "") == "1:8"
    repaired.close()
    stale = openpyxl.load_workbook(letter, data_only=True)
    assert stale["Index"]["H9"].value in (None, "")
    assert stale["Index"].page_setup.orientation == "landscape"
    assert int(stale["Index"].page_setup.paperSize) == 1
    stale.close()
    packet = json.loads(
        (receipts / "section15-index-packet.json").read_text(encoding="utf-8")
    )
    assert packet["candidate_rows"][0]["fields"]["legal_description"] == (
        "SYNTH TRACT 15-45N-76W"
    )
    joined = "\n".join(receipt.sections[0].next_commands)
    assert str(isolated) in joined
    assert "Working Abstract.xlsx" not in joined
    assert "--print-layout-output" not in joined
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    packet = json.loads(
        (receipts / "section15-index-packet.json").read_text(encoding="utf-8")
    )
    assert packet["candidate_rows"][0]["fields"]["legal_description"] == (
        "SYNTH TRACT 15-45N-76W"
    )


def test_reuse_delta_reruns_agreed_repairs_onto_next_isolated(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pc-root"
    section = root / "Section 15"
    _write_penterra(section / "Master Abstract.xlsx")
    _write_penterra(section / "County Index.xlsx")
    _write_penterra(section / "Handwritten Index.xlsx")
    _write_penterra(section / "Working Abstract.xlsx", legal="")
    faces = section / "Recorded Faces"
    faces.mkdir(parents=True, exist_ok=True)
    (faces / "Instrument 1.pdf").write_bytes(_minimal_pdf())
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    _write_penterra(receipts / "section15-letter.xlsx", legal="")
    current = receipts / "section15-delta.xlsx"
    _write_penterra(current, legal="")
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    unchanged = openpyxl.load_workbook(current, data_only=True)
    assert unchanged["Index"]["H9"].value in (None, "")
    unchanged.close()
    chained = receipts / "section15-delta-2.xlsx"
    assert chained.is_file()
    repaired = openpyxl.load_workbook(chained, data_only=True)
    assert repaired["Index"]["H9"].value == "SYNTH TRACT 15-45N-76W"
    repaired.close()


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
    assert drive_gate["detail"].get("isolated_copy") is not True
    plan = json.loads(
        (receipts / "section15-remaining-plan.json").read_text(encoding="utf-8")
    )
    assert (
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/"
        in plan["missing"]
    )
    assert any(
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/" in item
        for item in second.sections[0].next_commands
    )


def test_execute_does_not_use_other_section_letter_as_drive_readback(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    section13 = root / "Section 13"
    _write_penterra(section13 / "Master Abstract.xlsx")
    _write_penterra(section13 / "County Index.xlsx")
    _write_penterra(section13 / "Handwritten Index.xlsx")
    receipts = tmp_path / "private-receipts"
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15, 13],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    letter15 = receipts / "section15-letter.xlsx"
    letter13 = receipts / "section13-letter.xlsx"
    assert letter15.is_file() and letter13.is_file()
    # Independently written xlsx files differ by zip timestamp. Copy one
    # Letter over the other so the skip is tested at the same hash.
    letter13.write_bytes(letter15.read_bytes())
    planted = root / "Section 15" / "Isolated" / "section13-letter.xlsx"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_bytes(letter15.read_bytes())
    assert sha256_file(letter13) == sha256_file(letter15)
    assert sha256_file(planted) == sha256_file(letter15)
    bound15 = _same_hash_readback(None, letter15, receipts, 15)
    assert bound15 is None or bound15.resolve() != letter13.resolve()
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15, 13],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    bound15 = _same_hash_readback(None, letter15, receipts, 15)
    assert bound15 is None or bound15.resolve() not in {
        letter13.resolve(),
        planted.resolve(),
    }
    finish15 = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    drive15 = next(
        (gate for gate in finish15["gates"] if gate["name"] == "drive_readback"),
        None,
    )
    assert drive15 is None or drive15["technical_pass"] is not True
    assert (drive15 or {}).get("detail", {}).get("isolated_copy") is not True
    finish13 = json.loads(
        (receipts / "section13-finish.json").read_text(encoding="utf-8")
    )
    drive13 = next(
        (gate for gate in finish13["gates"] if gate["name"] == "drive_readback"),
        None,
    )
    if drive13 is not None and drive13.get("detail", {}).get("isolated_copy"):
        assert drive13["technical_pass"] is True
    bound13 = _same_hash_readback(None, letter13, receipts, 13)
    assert bound13 is None or bound13.resolve() != letter15.resolve()


def test_execute_does_not_reuse_other_section_drive_readback(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    section13 = root / "Section 13"
    _write_penterra(section13 / "Master Abstract.xlsx")
    _write_penterra(section13 / "County Index.xlsx")
    _write_penterra(section13 / "Handwritten Index.xlsx")
    receipts = tmp_path / "private-receipts"
    first = build_work_order(
        roots=[f"pc={root}"],
        sections=[15, 13],
        receipt_dir=receipts,
        execute=True,
    )
    assert first.packages_complete is False
    letter15 = receipts / "section15-letter.xlsx"
    letter13 = receipts / "section13-letter.xlsx"
    assert letter15.is_file() and letter13.is_file()
    letter13.write_bytes(letter15.read_bytes())
    planted = root / "Section 15" / "Isolated" / "section15-letter.xlsx"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_bytes(letter15.read_bytes())
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[15, 13],
        receipt_dir=receipts,
        execute=True,
        bindings=FinishBindings(drive_readback=planted),
    )
    assert second.packages_complete is False
    finish13 = json.loads(
        (receipts / "section13-finish.json").read_text(encoding="utf-8")
    )
    drive13 = next(
        (gate for gate in finish13["gates"] if gate["name"] == "drive_readback"),
        None,
    )
    assert drive13 is None or drive13.get("detail", {}).get("isolated_copy") is not True
    if drive13 is not None:
        dumped = json.dumps(drive13)
        assert "section15-letter.xlsx" not in dumped
    by_section = {order.section: order for order in second.sections}
    assert any(
        "different section Isolated" in hold for hold in by_section[13].holds
    )


def test_execute_publishes_section13_into_its_own_isolated_tree(
    tmp_path: Path,
) -> None:
    pc = tmp_path / "pc-root"
    drive = tmp_path / "drive-root"
    pc.mkdir()
    _section15_tree(pc)
    _section15_tree(drive)
    section13_pc = pc / "Section 13"
    _write_penterra(section13_pc / "Master Abstract.xlsx")
    _write_penterra(section13_pc / "County Index.xlsx")
    _write_penterra(section13_pc / "Handwritten Index.xlsx")
    section13_drive = drive / "Section 13"
    _write_penterra(section13_drive / "Master Abstract.xlsx")
    _write_penterra(section13_drive / "County Index.xlsx")
    _write_penterra(section13_drive / "Handwritten Index.xlsx")
    receipts = tmp_path / "private-receipts"
    first = build_work_order(
        roots=[f"pc={pc}", f"drive={drive}"],
        sections=[15, 13],
        receipt_dir=receipts,
        execute=True,
    )
    assert first.packages_complete is False
    letter13 = receipts / "section13-letter.xlsx"
    assert letter13.is_file()
    planted = drive / "Section 15" / "Isolated" / "section13-letter.xlsx"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_bytes(letter13.read_bytes())
    assert is_drive_isolated_copy(planted, 13) is False
    second = build_work_order(
        roots=[f"pc={pc}", f"drive={drive}"],
        sections=[15, 13],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    published = drive / "Section 13" / "Isolated" / "section13-letter.xlsx"
    assert published.is_file()
    assert published.read_bytes() == letter13.read_bytes()
    assert is_drive_isolated_copy(published, 13) is True
    finish13 = json.loads(
        (receipts / "section13-finish.json").read_text(encoding="utf-8")
    )
    drive13 = next(
        gate for gate in finish13["gates"] if gate["name"] == "drive_readback"
    )
    assert drive13["technical_pass"] is True
    assert drive13["detail"].get("isolated_copy") is True
    plan = json.loads(
        (receipts / "section13-remaining-plan.json").read_text(encoding="utf-8")
    )
    assert (
        "Copy section13-letter.xlsx into Drive Section 13/Isolated/"
        not in plan["missing"]
    )


def test_section_folder_dest_does_not_target_isolated(tmp_path: Path) -> None:
    drive = tmp_path / "drive"
    host = drive / "Section 15 Work" / "Section 13" / "Isolated"
    host.mkdir(parents=True)
    (drive / "Section 13" / "Isolated").mkdir(parents=True)
    (drive / "Isolated").mkdir()
    assert _section_folder_dest(
        drive,
        Path("Section 13/Isolated/section13-letter.xlsx"),
        13,
    ) == (drive / "Section 13").resolve()
    assert _section_folder_dest(
        drive,
        Path("Section 15 Work/Section 13/Isolated/section13-letter.xlsx"),
        13,
    ) == (drive / "Section 15 Work" / "Section 13").resolve()
    assert _section_folder_dest(
        drive, Path("Isolated/section13-letter.xlsx"), 13
    ) is None


def test_execute_does_not_publish_into_nested_isolated(tmp_path: Path) -> None:
    from horizon.source_acquisition import SourceRoot, build_receipt

    pc = tmp_path / "pc-root"
    drive = tmp_path / "drive-root"
    section13 = pc / "Section 13"
    _write_penterra(section13 / "Master Abstract.xlsx")
    _write_penterra(section13 / "County Index.xlsx")
    _write_penterra(section13 / "Handwritten Index.xlsx")
    host = drive / "Section 15 Work" / "Section 13"
    _write_penterra(host / "Master Abstract.xlsx")
    _write_penterra(host / "County Index.xlsx")
    _write_penterra(host / "Handwritten Index.xlsx")
    receipts = tmp_path / "private-receipts"
    first = build_work_order(
        roots=[f"pc={pc}", f"drive={drive}"],
        sections=[13],
        receipt_dir=receipts,
        execute=True,
    )
    assert first.packages_complete is False
    letter = receipts / "section13-letter.xlsx"
    assert letter.is_file()
    planted = host / "Isolated" / "section13-letter.xlsx"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_bytes(letter.read_bytes())
    inventory = build_receipt(
        [SourceRoot("drive", drive)],
        requested_sections=[13],
    )
    dest = _drive_section_dir(inventory, 13)
    assert dest is not None
    assert dest.name.casefold() != "isolated"
    assert dest == host.resolve()
    published, hold = _publish_isolated_to_drive(inventory, 13, letter)
    assert hold is None
    assert published == planted.resolve()
    assert not (planted.parent / "Isolated").exists()
    second = build_work_order(
        roots=[f"pc={pc}", f"drive={drive}"],
        sections=[13],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    assert not (host / "Isolated" / "Isolated").exists()
    assert planted.read_bytes() == letter.read_bytes()


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
    assert drive_gate["detail"].get("isolated_copy") is True
    plan = json.loads(
        (receipts / "section15-remaining-plan.json").read_text(encoding="utf-8")
    )
    assert (
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/"
        not in plan["missing"]
    )
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


def test_execute_upgrades_receipt_dir_readback_to_drive_isolated(
    tmp_path: Path,
) -> None:
    pc = tmp_path / "pc-root"
    drive = tmp_path / "drive-root"
    pc.mkdir()
    _section15_tree(pc)
    _section15_tree(drive)
    receipts = tmp_path / "private-receipts"
    first = build_work_order(
        roots=[f"pc={pc}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert first.packages_complete is False
    letter = receipts / "section15-letter.xlsx"
    copy = receipts / "drive-copy.xlsx"
    copy.write_bytes(letter.read_bytes())
    second = build_work_order(
        roots=[f"pc={pc}", f"drive={drive}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    published = drive / "Section 15" / "Isolated" / "section15-letter.xlsx"
    assert published.is_file()
    assert published.read_bytes() == letter.read_bytes()
    finish = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    drive_gate = next(
        gate for gate in finish["gates"] if gate["name"] == "drive_readback"
    )
    assert drive_gate["technical_pass"] is True
    assert drive_gate["detail"].get("isolated_copy") is True
    plan = json.loads(
        (receipts / "section15-remaining-plan.json").read_text(encoding="utf-8")
    )
    assert (
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/"
        not in plan["missing"]
    )
    assert not any(
        "Copy section15-letter.xlsx into Drive Section 15/Isolated/" in item
        for item in second.sections[0].next_commands
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
    assert not any(
        "create a human-approved authority manifest" in action
        for action in second.next_actions
    )
    assert not any(
        "cannot bind Phase 2" in action for action in second.next_actions
    )
    assert any(
        "cannot override the bound authority manifest" in action
        for action in second.next_actions
    )
    finish = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    acquisition = next(
        gate for gate in finish["gates"] if gate["name"] == "source_acquisition"
    )
    assert acquisition["technical_pass"] is True
    assert acquisition["detail"]["phase"] == "phase2_snapshot"
    assert second.sections[0].missing_required_roles == []
    plan = json.loads(
        (receipts / "section15-remaining-plan.json").read_text(encoding="utf-8")
    )
    assert plan["unauthorized_classified_roles"] == []
    assert plan["missing_required_roles"] == []
    assert not any("authority_promote" in item for item in plan["missing"])
    assert "Phase-2 authorized" not in "".join(plan["missing"])
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


def test_execute_keeps_native_print_packets_on_their_section(
    tmp_path: Path,
) -> None:
    from horizon.native_print import write_native_print_packet

    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    section13 = root / "Section 13"
    _write_penterra(section13 / "Master Abstract.xlsx")
    _write_penterra(section13 / "County Index.xlsx")
    _write_penterra(section13 / "Handwritten Index.xlsx")
    receipts = tmp_path / "private-receipts"
    first = build_work_order(
        roots=[f"pc={root}"],
        sections=[15, 13],
        receipt_dir=receipts,
        execute=True,
    )
    assert first.packages_complete is False
    write_native_print_packet(
        workbook=receipts / "section13-letter.xlsx",
        output=receipts / "section13-native-print.json",
        operator="Pat Examiner",
        page_count=1,
        expected_page_count=1,
        packet_id="SECTION13-PRINT",
    )
    write_native_print_packet(
        workbook=receipts / "section15-letter.xlsx",
        output=receipts / "section15-native-print.json",
        operator="Pat Examiner",
        page_count=1,
        expected_page_count=1,
        packet_id="SECTION15-PRINT",
    )
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[15, 13],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    by_section = {order.section: order for order in second.sections}
    for section in (15, 13):
        finish = json.loads(
            (receipts / f"section{section}-finish.json").read_text(encoding="utf-8")
        )
        native = next(
            gate for gate in finish["gates"] if gate["name"] == "native_print"
        )
        assert native["technical_pass"] is True
        assert all(
            "horizon.native_print" not in command
            for command in by_section[section].next_commands
        )
        assert all(
            "reprint the current isolated workbook" not in hold
            for hold in by_section[section].holds
        )


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
    names = [gate["name"] for gate in finish["gates"]]
    assert "workbook_qa" in names
    assert "isolated_delta" not in names
    recon = next(
        gate for gate in finish["gates"] if gate["name"] == "index_reconciliation"
    )
    assert recon["technical_pass"] is True
    assert recon["detail"]["blank_required_count"] == 0
    assert recon["detail"]["candidate_from"] == "workbook"
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


def test_delta_fill_rewrites_finish_when_follow_up_is_noop(
    tmp_path: Path,
) -> None:
    from horizon.isolated_delta import write_delta_packet

    root = tmp_path / "pc-root"
    section = root / "Section 15"
    _write_penterra(section / "Master Abstract.xlsx")
    _write_penterra(section / "County Index.xlsx")
    _write_penterra(section / "Handwritten Index.xlsx")
    _write_penterra(section / "Working Abstract.xlsx", legal="")
    (section / "Recorded Faces").mkdir(parents=True)
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(_minimal_pdf())
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    letter = receipts / "section15-letter.xlsx"
    _write_penterra(letter, legal="")
    write_delta_packet(
        workbook=letter,
        deltas=[
            {
                "row_key": "2026-09901|",
                "field": "legal_description",
                "value": "SYNTH TRACT 15-45N-76W",
                "source_sha256": "a" * 64,
                "page": 1,
                "crop_id": "legal",
                "replace": False,
            }
        ],
        output=receipts / "section15-delta-packet.json",
        packet_id="SYNTH-P15-DELTA-NOOP-FOLLOW",
    )
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    isolated = receipts / "section15-delta.xlsx"
    assert isolated.is_file()
    assert not (receipts / "section15-delta-2.xlsx").is_file()
    filled = openpyxl.load_workbook(isolated, data_only=True)
    assert filled["Index"]["H9"].value == "SYNTH TRACT 15-45N-76W"
    filled.close()
    payload = json.loads((receipts / "section15-finish.json").read_text())
    names = [gate["name"] for gate in payload["gates"]]
    assert "workbook_qa" in names
    assert "isolated_delta" not in names
    recon = next(
        gate for gate in payload["gates"] if gate["name"] == "index_reconciliation"
    )
    assert recon["technical_pass"] is True
    assert recon["detail"]["blank_required_count"] == 0
    assert recon["detail"]["candidate_from"] == "workbook"


def test_apply_delta_then_repairs_remaining_agreed_fills(
    tmp_path: Path,
) -> None:
    from horizon.isolated_delta import write_delta_packet

    root = tmp_path / "pc-root"
    section = root / "Section 15"
    _write_penterra(section / "Master Abstract.xlsx")
    _write_penterra(section / "County Index.xlsx")
    _write_penterra(section / "Handwritten Index.xlsx")
    _write_penterra(section / "Working Abstract.xlsx", legal="")
    (section / "Recorded Faces").mkdir(parents=True)
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(_minimal_pdf())
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    letter = receipts / "section15-letter.xlsx"
    _write_penterra(letter, legal="")
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
        packet_id="SYNTH-P15-FOLLOW-REPAIR",
    )
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    first = receipts / "section15-delta.xlsx"
    chained = receipts / "section15-delta-2.xlsx"
    assert first.is_file()
    assert chained.is_file()
    applied = openpyxl.load_workbook(first, data_only=True)
    assert applied["Index"]["I9"].value == "SYNTH SOURCE NOTE"
    applied.close()
    repaired = openpyxl.load_workbook(chained, data_only=True)
    assert repaired["Index"]["H9"].value == "SYNTH TRACT 15-45N-76W"
    assert repaired["Index"]["I9"].value == "SYNTH SOURCE NOTE"
    repaired.close()
    payload = json.loads((receipts / "section15-finish.json").read_text())
    names = [gate["name"] for gate in payload["gates"]]
    assert "workbook_qa" in names
    assert "isolated_delta" not in names
    qa = next(gate for gate in payload["gates"] if gate["name"] == "workbook_qa")
    assert qa["technical_pass"] is True


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
    assert draft["crops"][0]["docno"] == ""
    assert draft["crops"][0]["bookpage"] == ""
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
    assert draft["crops"][0]["docno"] == ""
    assert draft["crops"][0]["bookpage"] == ""
    assert draft["pages"][0]["source_sha256"] == sha256_file(page)
    queue_path = receipts / "section11-crop-fill-queue.json"
    assert queue_path.is_file()
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    assert queue["schema_id"] == "dbx.crop_fill_queue"
    assert queue["items"][0]["missing"][0] == "docno_or_bookpage"
    joined = "\n".join(receipt.sections[0].next_commands)
    assert "horizon.page_render_export" in joined
    assert "--attest" in joined
    assert "--from-draft" in joined
    assert str(renders.resolve()) in joined
    assert "14" not in draft["notes"][0]
    assert any(
        "face text" in hold for hold in receipt.sections[0].holds
    )


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


def test_operator_unbinds_stale_crop_packet_hashes(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    (root / "Section 11").mkdir(parents=True)
    receipts = tmp_path / "private-receipts"
    renders = receipts / "section11-renders"
    renders.mkdir(parents=True)
    (renders / "page-01.png").write_bytes(b"LIVE-RENDER")
    packet = {
        "schema_id": "dbx.page_render_crop_packet",
        "schema_version": "1.0",
        "packet_id": "SYNTH-P11-CROPS",
        "expected_page_count": 1,
        "pages": [
            {
                "page": 1,
                "path": "page-01.png",
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
    (receipts / "section11-crops.json").write_text(
        json.dumps(packet), encoding="utf-8"
    )
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[11],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    assert any(
        "do not match the current renders" in hold
        for hold in receipt.sections[0].holds
    )
    assert not (receipts / "section11-finish.json").is_file()


def test_crop_packet_without_paths_does_not_match_renders(tmp_path: Path) -> None:
    bind = tmp_path / "section11-renders"
    bind.mkdir()
    (bind / "page-01.png").write_bytes(b"LIVE-RENDER")
    packet = tmp_path / "section11-crops.json"
    packet.write_text(
        json.dumps(
            {
                "schema_id": "dbx.page_render_crop_packet",
                "schema_version": "1.0",
                "packet_id": "SECTION11-CROPS",
                "pages": [
                    {
                        "page": 1,
                        "source_sha256": "a" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert _crop_packet_matches_renders(packet, bind) is False


def test_execute_does_not_bind_other_section_crop_packet(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    (root / "Section 11").mkdir(parents=True)
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    (receipts / "section11-crops.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.page_render_crop_packet",
                "schema_version": "1.0",
                "packet_id": "SECTION11-CROPS",
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
        ),
        encoding="utf-8",
    )
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15, 11],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    finish15 = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    names15 = {gate["name"] for gate in finish15["gates"]}
    assert "page_render_export" not in names15
    finish11 = json.loads(
        (receipts / "section11-finish.json").read_text(encoding="utf-8")
    )
    names11 = {gate["name"] for gate in finish11["gates"]}
    assert "page_render_export" in names11


def test_discover_receipt_dir_packets_stays_on_named_section(tmp_path: Path) -> None:
    (tmp_path / "aaa-p13-print.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.native_print_receipt",
                "packet_id": "SECTION13-PRINT",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "zzz-p15-print.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.native_print_receipt",
                "packet_id": "SECTION15-PRINT",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "print-packet.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.native_print_receipt",
                "packet_id": "UNLABELED-PRINT",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "aaa-p13-census.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.pdf_page_census_packet",
                "packet_id": "SECTION13-CENSUS",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "section15-section13-census.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.pdf_page_census_packet",
                "packet_id": "SECTION15-CENSUS",
            }
        ),
        encoding="utf-8",
    )
    found15 = _discover_receipt_dir_packets(tmp_path, 15)
    found13 = _discover_receipt_dir_packets(tmp_path, 13)
    assert found15["native_print_receipt"].name == "zzz-p15-print.json"
    assert found13["native_print_receipt"].name == "aaa-p13-print.json"
    assert found13["pdf_census_packet"].name == "aaa-p13-census.json"
    assert "pdf_census_packet" not in found15
    assert all(
        path.name != "section15-section13-census.json"
        for path in (*found15.values(), *found13.values())
    )
    assert all(
        path.name != "print-packet.json" for path in found15.values()
    )
    assert all(
        path.name != "print-packet.json" for path in found13.values()
    )


def test_discover_owner_review_stays_on_token_sections(tmp_path: Path) -> None:
    (tmp_path / "section15-owner-review.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.human_release_token",
                "packet_id": "SECTION15-OWNER-REVIEW",
                "sections": [15, 13],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "section13-owner-review.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.human_release_token",
                "packet_id": "SECTION13-OWNER-REVIEW",
                "sections": [13],
            }
        ),
        encoding="utf-8",
    )
    found15 = _discover_receipt_dir_packets(tmp_path, 15)
    found13 = _discover_receipt_dir_packets(tmp_path, 13)
    assert "human_release_token" not in found15
    assert found13["human_release_token"].name == "section13-owner-review.json"


def test_section_packets_prefer_conventional_over_leftover(
    tmp_path: Path,
) -> None:
    leftover_print = tmp_path / "aaa-p15-print.json"
    leftover_print.write_text(
        json.dumps(
            {
                "schema_id": "dbx.native_print_receipt",
                "packet_id": "SECTION15-PRINT",
            }
        ),
        encoding="utf-8",
    )
    conventional_print = tmp_path / "section15-native-print.json"
    conventional_print.write_text(
        json.dumps(
            {
                "schema_id": "dbx.native_print_receipt",
                "packet_id": "SECTION15-PRINT",
            }
        ),
        encoding="utf-8",
    )
    leftover_crops = tmp_path / "aaa-p11-crops.json"
    leftover_crops.write_text(
        json.dumps(
            {
                "schema_id": "dbx.page_render_crop_packet",
                "packet_id": "SECTION11-CROPS",
            }
        ),
        encoding="utf-8",
    )
    conventional_crops = tmp_path / "section11-crops.json"
    conventional_crops.write_text(
        json.dumps(
            {
                "schema_id": "dbx.page_render_crop_packet",
                "packet_id": "SECTION11-CROPS",
            }
        ),
        encoding="utf-8",
    )
    leftover_census = tmp_path / "aaa-p15-census.json"
    leftover_census.write_text(
        json.dumps(
            {
                "schema_id": "dbx.pdf_page_census_packet",
                "packet_id": "SECTION15-CENSUS",
            }
        ),
        encoding="utf-8",
    )
    conventional_census = tmp_path / "section15-pdf-census-packet.json"
    conventional_census.write_text(
        json.dumps(
            {
                "schema_id": "dbx.pdf_page_census_packet",
                "packet_id": "SECTION15-CENSUS",
            }
        ),
        encoding="utf-8",
    )
    assert (
        _section_named_packet(
            leftover_print,
            str(tmp_path),
            15,
            "dbx.native_print_receipt",
            "section15-native-print.json",
        )
        == conventional_print
    )
    assert _section_crop_packet(leftover_crops, str(tmp_path), 11) == conventional_crops
    assert (
        _section_census_packet(leftover_census, str(tmp_path), 15)
        == conventional_census
    )


def test_section_census_packet_oserror_does_not_return_other_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    leftover = tmp_path / "aaa-p13-census.json"
    leftover.write_text(
        json.dumps(
            {
                "schema_id": "dbx.pdf_page_census_packet",
                "packet_id": "SECTION13-CENSUS",
            }
        ),
        encoding="utf-8",
    )

    def boom(path: Path, section: int) -> bool:
        if path.name.startswith(f"section{section}"):
            raise OSError("unavailable")
        return False

    monkeypatch.setattr(
        "horizon.pc_operator._census_packet_matches_section", boom
    )
    assert _section_census_packet(leftover, str(tmp_path), 15) is None


def test_bind_dir_stays_on_named_section(tmp_path: Path) -> None:
    named15 = tmp_path / "section15-pdfs"
    named13 = tmp_path / "section13-renders"
    unlabeled = tmp_path / "faces"
    dual = tmp_path / "section15-section13-pdfs"
    for path in (named15, named13, unlabeled, dual):
        path.mkdir()
    assert _bind_dir_for_section(named15, 15) == named15
    assert _bind_dir_for_section(named15, 13) is None
    assert _bind_dir_for_section(named13, 13) == named13
    assert _bind_dir_for_section(named13, 15) is None
    assert _bind_dir_for_section(unlabeled, 15) is None
    assert _bind_dir_for_section(dual, 15) is None
    assert _bind_dir_for_section(dual, 13) is None
    assert _bind_dir_for_section(None, 15) is None


def test_execute_does_not_reuse_other_section_pdf_bind_dir(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    section13 = root / "Section 13"
    _write_penterra(section13 / "Master Abstract.xlsx")
    _write_penterra(section13 / "County Index.xlsx")
    _write_penterra(section13 / "Handwritten Index.xlsx")
    receipts = tmp_path / "private-receipts"
    other_pdfs = receipts / "section15-pdfs"
    other_pdfs.mkdir(parents=True)
    (other_pdfs / "part4.pdf").write_bytes(_minimal_pdf())
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15, 13],
        receipt_dir=receipts,
        execute=True,
        bindings=FinishBindings(pdf_bind_dir=other_pdfs),
    )
    assert receipt.packages_complete is False
    finish13 = json.loads(
        (receipts / "section13-finish.json").read_text(encoding="utf-8")
    )
    assert "pdf_census" not in {gate["name"] for gate in finish13["gates"]}
    dumped = json.dumps(finish13)
    assert "462" not in dumped
    assert "SECTION15" not in dumped
    assert not (receipts / "section13-empty-text-queue.json").exists()
    assert not (receipts / "section13-pdf-census-packet.json").exists()


def test_execute_does_not_bind_other_section_census_packet(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    root.mkdir()
    _section15_tree(root)
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    (receipts / "aaa-p13-census.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.pdf_page_census_packet",
                "schema_version": "1.0",
                "packet_id": "SECTION13-CENSUS",
                "files": [
                    {
                        "path": "part4.pdf",
                        "source_sha256": "a" * 64,
                        "expected_pages": 462,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    finish = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    assert "pdf_census" not in {gate["name"] for gate in finish["gates"]}
    dumped = json.dumps(finish)
    assert "462" not in dumped
    assert "SECTION13-CENSUS" not in dumped
    assert not (receipts / "section15-empty-text-queue.json").exists()
    assert all(
        "pdf_census --inventory" in command
        or "--pdf-census-packet" not in command
        for command in receipt.sections[0].next_commands
    )


def test_execute_discovers_named_print_after_other_section_leftover(
    tmp_path: Path,
) -> None:
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
        output=receipts / "aaa-p13-print.json",
        operator="Pat Examiner",
        page_count=1,
        expected_page_count=1,
        packet_id="SECTION13-PRINT",
    )
    write_native_print_packet(
        workbook=letter,
        output=receipts / "zzz-p15-print.json",
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
    finish = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    native = next(gate for gate in finish["gates"] if gate["name"] == "native_print")
    assert native["technical_pass"] is True
    assert all(
        "horizon.native_print" not in command
        for command in second.sections[0].next_commands
    )


def test_execute_does_not_apply_other_section_delta_packet(tmp_path: Path) -> None:
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
    assert letter.is_file()
    digest = sha256_file(letter)
    (receipts / "section11-deltas.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_proved_delta_packet",
                "schema_version": "1.0",
                "packet_id": "SECTION11-DELTA",
                "source_workbook_sha256": digest,
                "deltas": [
                    {
                        "row_key": "2026-09901|",
                        "field": "comments",
                        "value": "DO NOT APPLY TO SECTION 15",
                        "source_sha256": "a" * 64,
                        "page": 1,
                        "crop_id": "c1",
                        "replace": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    before = set(receipts.glob("section15-delta*.xlsx"))
    second = build_work_order(
        roots=[f"pc={root}"],
        sections=[15],
        receipt_dir=receipts,
        execute=True,
    )
    assert second.packages_complete is False
    assert set(receipts.glob("section15-delta*.xlsx")) == before
    finish = json.loads(
        (receipts / "section15-finish.json").read_text(encoding="utf-8")
    )
    assert "isolated_delta" not in {gate["name"] for gate in finish["gates"]}
    dumped = json.dumps(finish)
    assert "DO NOT APPLY TO SECTION 15" not in dumped


def test_execute_passes_crop_bind_dir_for_attested_renders(tmp_path: Path) -> None:
    root = tmp_path / "pc-root"
    (root / "Section 11").mkdir(parents=True)
    receipts = tmp_path / "private-receipts"
    renders = receipts / "section11-renders"
    renders.mkdir(parents=True)
    render = renders / "page-01.png"
    render.write_bytes(b"LIVE-RENDER")
    digest = sha256_file(render)
    (receipts / "section11-crops.json").write_text(
        json.dumps(
            {
                "schema_id": "dbx.page_render_crop_packet",
                "schema_version": "1.0",
                "packet_id": "SECTION11-CROPS",
                "expected_page_count": 1,
                "pages": [
                    {
                        "page": 1,
                        "path": "page-01.png",
                        "source_sha256": digest,
                    }
                ],
                "crops": [
                    {
                        "row_id": "p01r01",
                        "page": 1,
                        "crop_id": "p01r01",
                        "source_sha256": digest,
                        "docno": "2026-09901",
                        "bookpage": "",
                        "rec_date": "1/2/2026",
                        "doc_date": "",
                        "grantor": "SYNTH SURVEYOR",
                        "grantee": "The Public",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    receipt = build_work_order(
        roots=[f"pc={root}"],
        sections=[11],
        receipt_dir=receipts,
        execute=True,
    )
    assert receipt.packages_complete is False
    finish = json.loads(
        (receipts / "section11-finish.json").read_text(encoding="utf-8")
    )
    export = next(
        gate for gate in finish["gates"] if gate["name"] == "page_render_export"
    )
    assert export["technical_pass"] is True
    assert export.get("error") in (None, "")


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
    queue_path = receipts / "section13-empty-text-queue.json"
    assert queue_path.is_file()
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    assert queue["schema_id"] == "dbx.empty_text_pdf_queue"
    assert queue["items"][0]["path"] == "part4.pdf"
    assert queue["items"][0]["action"] == "face_review"
    assert "462" not in json.dumps(queue)
    assert any(
        "empty extracted text" in hold for hold in receipt.sections[0].holds
    )
    assert (receipts / "section13-pdf-census-receipt.json").is_file()
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
