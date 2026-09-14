"""Package finish runner never promotes and chains existing gates."""

import hashlib
import json
from pathlib import Path

import openpyxl
import pytest

from horizon.human_release import OWNER_REVIEW_STATEMENT
from horizon.isolated_delta import sha256_file
from horizon.package_finish import PackageFinishError, main, run_finish
from horizon.workbook_qa import inspect_workbook, load_workbook_profile


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
PENTERRA_PROFILE = (
    Path(__file__).resolve().parents[1]
    / "horizon"
    / "profiles"
    / "penterra_index_v1.json"
)


def _penterra_workbook(path: Path, *, blank_legal: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Index"
    for label in (
        "Index County",
        "Lands",
        "Date",
        "Starting Date",
        "Date Posted Thru",
        "Indexed By",
        "Project",
    ):
        sheet.append([label, "SYNTH"])
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
            "" if blank_legal else "SYNTH TRACT 15-45N-76W",
            "",
        ]
    )
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_LETTER
    sheet.print_title_rows = "1:8"
    workbook.save(path)
    workbook.close()


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _checkable_export() -> dict:
    return {
        "schema_id": "dbx.tract_ledger_export",
        "schema_version": "1.0",
        "packet_id": "SYNTH-FINISH-001",
        "rows": [
            {
                "row_id": "p01r01",
                "docno": "2026-09901",
                "bookpage": "",
                "rec_date": "1/2/2026",
                "doc_date": "",
                "grantor": "SYNTH SURVEYOR",
                "grantee": "The Public",
                "page": 1,
                "crop_id": "p01r01",
            }
        ],
    }


def _occurrence_packet() -> dict:
    key = "2026-09901|"
    digest = _sha("face-a")
    fields = {
        "party": "SYNTH SURVEYOR",
        "date_role": "recorded",
        "legal": "SYNTH TRACT",
    }
    return {
        "schema_id": "dbx.occurrence_packet",
        "schema_version": "1.0",
        "packet_id": "SYNTH-FINISH-OCC",
        "occurrences": [
            {
                "occurrence_id": "occ-001",
                "stable_key": key,
                "source_sha256": digest,
                "page": 1,
                "crop_id": "p01r01",
                "fields": fields,
                "risk": "novel",
            }
        ],
        "unique_key_ledger": [{"stable_key": key, "source_sha256": digest}],
        "candidate_rows": [
            {
                "row_id": "R6-001",
                "stable_key": key,
                "source_sha256": digest,
                "fields": fields,
            }
        ],
        "allowlist": [],
    }


def test_empty_run_is_blocked_and_never_complete() -> None:
    receipt = run_finish(sections=[15, 13, 11])
    assert receipt.packages_complete is False
    assert receipt.technical_pass is False
    assert receipt.gates == []
    assert any("Mount PC/Drive" in action for action in receipt.next_actions)


def test_chained_checkable_packets_pass_gates_but_not_packages(
    tmp_path: Path,
) -> None:
    export = tmp_path / "export.json"
    packet = tmp_path / "packet.json"
    plat = tmp_path / "plat.pdf"
    export.write_text(json.dumps(_checkable_export()), encoding="utf-8")
    packet.write_text(json.dumps(_occurrence_packet()), encoding="utf-8")
    plat.write_bytes(b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n")

    receipt = run_finish(
        sections=[15, 13, 11],
        tract_export=export,
        occurrence_packet=packet,
        public_plats=[f"campbell,45n,76w,{plat}"],
    )
    assert receipt.technical_pass is True
    assert receipt.packages_complete is False
    assert {gate.name for gate in receipt.gates} == {
        "reextraction",
        "occurrence_ledger",
        "public_cadastral",
    }
    assert all(gate.technical_pass for gate in receipt.gates)


def test_penterra_profile_blocks_blank_legal(tmp_path: Path) -> None:
    workbook = tmp_path / "index.xlsx"
    _penterra_workbook(workbook, blank_legal=True)
    report = inspect_workbook(
        workbook,
        ["abstract_required_fields"],
        profile=load_workbook_profile(PENTERRA_PROFILE),
    )
    assert not report.score.technical_pass
    assert any(
        finding.code == "abstract_required_field_blank"
        and finding.cell == "H9"
        for finding in report.findings
    )


def test_a4_index_fails_letter_print_layout(tmp_path: Path) -> None:
    workbook = tmp_path / "index.xlsx"
    _penterra_workbook(workbook)
    loaded = openpyxl.load_workbook(workbook)
    loaded["Index"].page_setup.paperSize = loaded["Index"].PAPERSIZE_A4
    loaded.save(workbook)
    loaded.close()
    receipt = run_finish(sections=[15], workbook=workbook)
    assert receipt.packages_complete is False
    assert receipt.technical_pass is False
    qa = next(gate for gate in receipt.gates if gate.name == "workbook_qa")
    assert qa.technical_pass is False
    assert any(
        finding["code"] == "abstract_layout_mismatch"
        and finding["cell"] == ""
        for finding in qa.detail["findings"]
    )


def _index_packet() -> dict:
    key = "2026-09901|"
    fields = {
        "document_type": "Mineral Deed",
        "grantor": "SYNTH ALPHA LLC",
        "grantee": "SYNTH BETA LLC",
        "recorded_date": "1/2/2026",
        "legal_description": "SYNTH TRACT 15-45N-76W",
    }
    face = {
        "stable_key": key,
        "source_sha256": _sha("recon-face"),
        "page": 1,
        "crop_id": "recon",
        "fields": fields,
    }
    return {
        "schema_id": "dbx.index_reconciliation_packet",
        "schema_version": "1.0",
        "packet_id": "SYNTH-FINISH-RECON",
        "master": [face],
        "pdf_index": [dict(face, source_sha256=_sha("recon-pdf"))],
        "handwritten_index": [dict(face, source_sha256=_sha("recon-hand"))],
        "candidate_rows": [dict(face, source_sha256=_sha("recon-cand"))],
        "expected_counts": {
            "master": 1,
            "pdf_index": 1,
            "handwritten_index": 1,
            "candidate_rows": 1,
        },
        "orphan_allowlist": [],
    }


def test_three_workbooks_reconcile_without_a_packet_file(tmp_path: Path) -> None:
    master = tmp_path / "master.xlsx"
    pdf = tmp_path / "pdf.xlsx"
    hand = tmp_path / "hand.xlsx"
    candidate = tmp_path / "candidate.xlsx"
    _penterra_workbook(master)
    _penterra_workbook(pdf)
    _penterra_workbook(hand)
    _penterra_workbook(candidate)
    receipt = run_finish(
        sections=[15],
        workbook=candidate,
        master_workbook=master,
        pdf_workbook=pdf,
        handwritten_workbook=hand,
    )
    assert receipt.packages_complete is False
    names = [gate.name for gate in receipt.gates]
    assert names[0] == "index_reconciliation"
    assert "workbook_qa" in names
    recon = receipt.gates[0]
    assert recon.technical_pass is True
    assert recon.detail["built_from"] == "source_workbooks"
    assert recon.detail["proposed_delta_count"] == 0


def test_index_packet_recon_uses_workbook_candidate(tmp_path: Path) -> None:
    packet = _index_packet()
    packet["candidate_rows"][0]["fields"]["legal_description"] = ""
    packet_path = tmp_path / "indexes.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    workbook = tmp_path / "isolated.xlsx"
    _penterra_workbook(workbook)
    stale = run_finish(sections=[15], index_packet=packet_path)
    assert stale.packages_complete is False
    recon = next(
        gate for gate in stale.gates if gate.name == "index_reconciliation"
    )
    assert recon.detail["blank_required_count"] >= 1
    assert recon.detail["candidate_from"] == "index_packet"
    refreshed = run_finish(
        sections=[15],
        workbook=workbook,
        index_packet=packet_path,
    )
    assert refreshed.packages_complete is False
    recon = next(
        gate for gate in refreshed.gates if gate.name == "index_reconciliation"
    )
    assert recon.technical_pass is True
    assert recon.detail["blank_required_count"] == 0
    assert recon.detail["conflict_count"] == 0
    assert recon.detail["candidate_from"] == "workbook"


def test_index_packet_and_source_workbooks_conflict_without_repair(
    tmp_path: Path,
) -> None:
    packet = tmp_path / "index.json"
    master = tmp_path / "master.xlsx"
    packet.write_text(json.dumps(_index_packet()), encoding="utf-8")
    _penterra_workbook(master)
    with pytest.raises(PackageFinishError, match="not both"):
        run_finish(
            sections=[15],
            index_packet=packet,
            master_workbook=master,
        )


def test_index_reconciliation_gate_scores_fields_without_completing_packages(
    tmp_path: Path,
) -> None:
    packet = tmp_path / "index.json"
    packet.write_text(json.dumps(_index_packet()), encoding="utf-8")
    receipt = run_finish(sections=[15, 13, 11], index_packet=packet)
    assert receipt.packages_complete is False
    assert receipt.technical_pass is True
    gate = receipt.gates[0]
    assert gate.name == "index_reconciliation"
    assert gate.detail["conflict_count"] == 0
    assert gate.detail["proposed_delta_count"] == 0


def test_workbook_gate_runs_on_isolated_penterra_index(tmp_path: Path) -> None:
    workbook = tmp_path / "index.xlsx"
    _penterra_workbook(workbook)
    receipt = run_finish(sections=[15], workbook=workbook)
    assert receipt.packages_complete is False
    assert receipt.technical_pass is True
    assert receipt.gates[0].name == "workbook_qa"
    assert receipt.gates[0].technical_pass is True


def test_delta_fill_then_qa_runs_on_copy_not_source(tmp_path: Path) -> None:
    source = tmp_path / "index.xlsx"
    isolated = tmp_path / "index-filled.xlsx"
    packet = tmp_path / "delta.json"
    _penterra_workbook(source, blank_legal=True)
    packet.write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_proved_delta_packet",
                "schema_version": "1.0",
                "packet_id": "SYNTH-FINISH-DELTA",
                "source_workbook_sha256": sha256_file(source),
                "deltas": [
                    {
                        "row_key": "2026-09901|",
                        "field": "legal_description",
                        "value": "SYNTH TRACT 15-45N-76W",
                        "source_sha256": _sha("face-legal"),
                        "page": 1,
                        "crop_id": "legal",
                        "replace": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    receipt = run_finish(
        sections=[15],
        workbook=source,
        delta_packet=packet,
        delta_output=isolated,
    )
    assert receipt.packages_complete is False
    assert receipt.technical_pass is True
    assert {gate.name for gate in receipt.gates} == {
        "isolated_delta",
        "workbook_qa",
        "reextraction",
        "occurrence_ledger",
    }
    assert all(gate.technical_pass for gate in receipt.gates)
    source_wb = openpyxl.load_workbook(source, data_only=True)
    isolated_wb = openpyxl.load_workbook(isolated, data_only=True)
    assert source_wb["Index"]["H9"].value in (None, "")
    assert isolated_wb["Index"]["H9"].value == "SYNTH TRACT 15-45N-76W"
    source_wb.close()
    isolated_wb.close()


def _write_authority_pair(
    tmp_path: Path,
    root: Path,
    *,
    section: int = 15,
) -> tuple[Path, Path]:
    files = {
        "master_workbook": f"Section {section}/Master Abstract.xlsx",
        "index": f"Section {section}/County Index.xlsx",
        "handwritten_index": f"Section {section}/Handwritten Index.xlsx",
        "source_document": f"Section {section}/Recorded Faces/Instrument 1.pdf",
    }
    authorities = [
        {
            "root_label": "pc",
            "relative_path": relative,
            "section": section,
            "role": role,
            "expected_sha256": sha256_file(root / relative),
        }
        for role, relative in files.items()
    ]
    authority = tmp_path / "authority.json"
    authority.write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_authority_manifest",
                "schema_version": "1.0",
                "project_id": "DBX-TEST",
                "decision_id": "SOURCE-AUTH-001",
                "approved_by": "Synthetic Test Examiner",
                "authorities": authorities,
            }
        ),
        encoding="utf-8",
    )
    project = tmp_path / "project_manifest.json"
    project.write_text(
        json.dumps(
            {
                "schema_id": "dbx.project_manifest",
                "schema_version": "1.1",
                "project_id": "DBX-TEST",
                "source_policy": "IMMUTABLE_READ_ONLY",
                "authority_hashes": {"source_authority": sha256_file(authority)},
                "candidate_deliverables": [
                    {
                        "path": "candidate.xlsx",
                        "reported_sha256": "0" * 64,
                        "status": "CANDIDATE",
                    }
                ],
                "required_checks": ["source_acquisition"],
                "release_policy": {
                    "technical_verification_is_not_release": True,
                    "approved_hash_required": True,
                    "human_gate": "G7",
                },
            }
        ),
        encoding="utf-8",
    )
    return authority, project


def test_combined_authority_is_filtered_to_requested_section(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pc"
    for section in (15, 13):
        _penterra_workbook(root / f"Section {section}" / "Master Abstract.xlsx")
        _penterra_workbook(root / f"Section {section}" / "County Index.xlsx")
        _penterra_workbook(root / f"Section {section}" / "Handwritten Index.xlsx")
        faces = root / f"Section {section}" / "Recorded Faces"
        faces.mkdir(parents=True, exist_ok=True)
        (faces / "Instrument 1.pdf").write_bytes(b"%PDF-1.1 synth")
    files = []
    for section in (15, 13):
        files.extend(
            [
                (
                    "master_workbook",
                    f"Section {section}/Master Abstract.xlsx",
                    section,
                ),
                ("index", f"Section {section}/County Index.xlsx", section),
                (
                    "handwritten_index",
                    f"Section {section}/Handwritten Index.xlsx",
                    section,
                ),
                (
                    "source_document",
                    f"Section {section}/Recorded Faces/Instrument 1.pdf",
                    section,
                ),
            ]
        )
    authority = tmp_path / "authority.json"
    authority.write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_authority_manifest",
                "schema_version": "1.0",
                "project_id": "DBX-TEST",
                "decision_id": "SOURCE-AUTH-001",
                "approved_by": "Synthetic Test Examiner",
                "authorities": [
                    {
                        "root_label": "pc",
                        "relative_path": relative,
                        "section": section,
                        "role": role,
                        "expected_sha256": sha256_file(root / relative),
                    }
                    for role, relative, section in files
                ],
            }
        ),
        encoding="utf-8",
    )
    project = tmp_path / "project_manifest.json"
    project.write_text(
        json.dumps(
            {
                "schema_id": "dbx.project_manifest",
                "schema_version": "1.1",
                "project_id": "DBX-TEST",
                "source_policy": "IMMUTABLE_READ_ONLY",
                "authority_hashes": {"source_authority": sha256_file(authority)},
                "candidate_deliverables": [
                    {
                        "path": "candidate.xlsx",
                        "reported_sha256": "0" * 64,
                        "status": "CANDIDATE",
                    }
                ],
                "required_checks": ["source_acquisition"],
                "release_policy": {
                    "technical_verification_is_not_release": True,
                    "approved_hash_required": True,
                    "human_gate": "G7",
                },
            }
        ),
        encoding="utf-8",
    )
    receipt = run_finish(
        sections=[15],
        roots=[f"pc={root}"],
        authority_manifest=authority,
        project_manifest=project,
        snapshot_directory=tmp_path / "snapshot",
    )
    gate = next(item for item in receipt.gates if item.name == "source_acquisition")
    assert gate.technical_pass is True
    assert receipt.packages_complete is False


def test_phase_two_authority_can_pass_acquisition(tmp_path: Path) -> None:
    root = tmp_path / "pc"
    section = root / "Section 15"
    _penterra_workbook(section / "Master Abstract.xlsx")
    _penterra_workbook(section / "County Index.xlsx")
    _penterra_workbook(section / "Handwritten Index.xlsx")
    (section / "Recorded Faces").mkdir(parents=True)
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(b"%PDF-1.1 synth")
    authority, project = _write_authority_pair(tmp_path, root)
    receipt = run_finish(
        sections=[15],
        roots=[f"pc={root}"],
        authority_manifest=authority,
        project_manifest=project,
        snapshot_directory=tmp_path / "snapshot",
    )
    assert receipt.packages_complete is False
    gate = next(item for item in receipt.gates if item.name == "source_acquisition")
    assert gate.technical_pass is True
    assert gate.detail["phase"] == "phase2_snapshot"


def test_writer_held_evidence_can_complete_one_synthetic_section(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pc"
    section = root / "Section 15"
    master = section / "Master Abstract.xlsx"
    pdf = section / "County Index.xlsx"
    hand = section / "Handwritten Index.xlsx"
    candidate = section / "Working Abstract.xlsx"
    _penterra_workbook(master)
    _penterra_workbook(pdf)
    _penterra_workbook(hand)
    _penterra_workbook(candidate)
    (section / "Recorded Faces").mkdir(parents=True)
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(b"%PDF-1.1 synth")
    authority, project = _write_authority_pair(tmp_path, root)
    digest = sha256_file(candidate)
    native = tmp_path / "native.json"
    native.write_text(
        json.dumps(
            {
                "schema_id": "dbx.native_print_receipt",
                "schema_version": "1.0",
                "packet_id": "SYNTH-P15-PRINT",
                "workbook_sha256": digest,
                "application": "Microsoft Excel",
                "host": "Windows",
                "paper_size": 1,
                "orientation": "landscape",
                "page_count": 2,
                "expected_page_count": 2,
                "print_titles": True,
                "print_area_set": True,
                "operator": "SYNTH OPERATOR",
            }
        ),
        encoding="utf-8",
    )
    drive = tmp_path / "drive-copy.xlsx"
    drive.write_bytes(candidate.read_bytes())
    release = tmp_path / "release.json"
    release.write_text(
        json.dumps(
            {
                "schema_id": "dbx.human_release_token",
                "schema_version": "1.0",
                "packet_id": "SYNTH-RELEASE",
                "sections": [15],
                "operator": "SYNTH OPERATOR",
                "workbook_sha256": digest,
                "statement": OWNER_REVIEW_STATEMENT,
                "external_release": False,
            }
        ),
        encoding="utf-8",
    )
    receipt = run_finish(
        sections=[15],
        roots=[f"pc={root}"],
        connect_status=True,
        authority_manifest=authority,
        project_manifest=project,
        snapshot_directory=tmp_path / "snapshot",
        workbook=candidate,
        master_workbook=master,
        pdf_workbook=pdf,
        handwritten_workbook=hand,
        native_print_receipt=native,
        drive_readback=drive,
        human_release_token=release,
    )
    assert receipt.packages_complete is True
    assert receipt.technical_pass is True
    reextraction = next(
        gate for gate in receipt.gates if gate.name == "reextraction"
    )
    assert reextraction.detail.get("built_from") == "workbook"
    occurrence = next(
        gate for gate in receipt.gates if gate.name == "occurrence_ledger"
    )
    assert occurrence.detail.get("built_from") == "workbook"


def test_cli_empty_run_writes_blocked_receipt(tmp_path: Path) -> None:
    output = tmp_path / "finish.json"
    result = main(["--output", str(output), "--section", "15"])
    assert result == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["packages_complete"] is False
    assert payload["technical_pass"] is False
