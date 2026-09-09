"""Tests for read-only, fail-closed section source acquisition receipts."""

import json
from pathlib import Path
from typing import Optional

import pytest

import horizon.source_acquisition as source_acquisition
from horizon.source_acquisition import (
    SourceAcquisitionError,
    SourceRoot,
    build_receipt,
    detect_section,
    main,
    write_receipt,
)


def _write(root: Path, relative_path: str, content: bytes = b"evidence") -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _complete_section(root: Path, section: int, prefix: str = "") -> None:
    section_root = f"{prefix}Section {section}"
    _write(root, f"{section_root}/Master Abstract.xlsx", b"master")
    _write(root, f"{section_root}/County Index.pdf", b"index")
    _write(root, f"{section_root}/Recorded Faces/Instrument 1.pdf", b"face")


def test_exact_pc_drive_sources_are_ready_for_extraction(tmp_path: Path) -> None:
    pc = tmp_path / "pc"
    drive = tmp_path / "drive"
    _complete_section(pc, 15)
    _complete_section(drive, 15)

    receipt = build_receipt(
        [SourceRoot("pc", pc), SourceRoot("drive", drive)],
        requested_sections=[15],
    )

    assert receipt.technical_pass
    assert receipt.sections[0].ready_for_extraction
    assert {comparison.status for comparison in receipt.path_comparisons} == {
        "exact_match"
    }
    assert len(receipt.duplicate_content) == 3


def test_same_relative_path_with_different_hash_blocks_intake(
    tmp_path: Path,
) -> None:
    pc = tmp_path / "pc"
    drive = tmp_path / "drive"
    _complete_section(pc, 15)
    _complete_section(drive, 15)
    _write(drive, "Section 15/Master Abstract.xlsx", b"conflicting master")

    receipt = build_receipt(
        [SourceRoot("pc", pc), SourceRoot("drive", drive)],
        requested_sections=[15],
    )

    assert not receipt.technical_pass
    assert receipt.sections[0].conflicting_paths == 1
    assert any(
        comparison.status == "hash_conflict"
        and comparison.relative_path == "Section 15/Master Abstract.xlsx"
        for comparison in receipt.path_comparisons
    )


def test_missing_priority_sections_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)

    receipt = build_receipt([SourceRoot("local", root)])

    assert not receipt.technical_pass
    by_section = {summary.section: summary for summary in receipt.sections}
    assert by_section[15].ready_for_extraction
    assert not by_section[13].ready_for_extraction
    assert not by_section[11].ready_for_extraction
    assert by_section[13].missing_required_roles == [
        "source_document",
        "master_workbook",
        "index",
    ]


def test_handwritten_index_satisfies_index_role(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _write(root, "Section 13/Master Abstract.xlsx", b"master")
    _write(root, "Section 13/Handwritten Index.tif", b"scan")
    _write(root, "Section 13/Recorded Face.pdf", b"face")

    receipt = build_receipt(
        [SourceRoot("local", root)],
        requested_sections=[13],
    )

    assert receipt.technical_pass
    assert receipt.sections[0].role_counts["handwritten_index"] == 1


@pytest.mark.parametrize(
    ("relative_path", "expected"),
    [
        ("Section 15/Master.xlsx", 15),
        ("sec_13/index.pdf", 13),
        ("11-45N-76W/Abstract/report.xlsx", 11),
        ("instrument-2024-00115.pdf", None),
        ("Section 150/source.pdf", None),
        ("Section 15x/source.pdf", None),
        ("Section 12/source.pdf", None),
    ],
)
def test_section_detection_requires_explicit_priority_section(
    relative_path: str,
    expected: Optional[int],
) -> None:
    assert detect_section(relative_path) == expected


def test_duplicate_content_at_different_paths_is_reported(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    _write(root, "Section 15/Recorded Faces/copy.pdf", b"face")

    receipt = build_receipt(
        [SourceRoot("local", root)],
        requested_sections=[15],
    )

    face_hash = next(
        item.sha256
        for item in receipt.files
        if item.relative_path.endswith("Instrument 1.pdf")
    )
    duplicate = next(
        group for group in receipt.duplicate_content
        if group["sha256"] == face_hash
    )
    assert len(duplicate["locations"]) == 2


def test_symlinked_source_is_rejected_and_blocks_intake(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    outside = _write(tmp_path, "outside.pdf", b"outside")
    link = root / "Section 15" / "linked.pdf"
    link.symlink_to(outside)

    receipt = build_receipt(
        [SourceRoot("local", root)],
        requested_sections=[15],
    )

    assert not receipt.technical_pass
    assert receipt.issues[0].code == "source_symlink_rejected"
    assert receipt.issues[0].relative_path == "Section 15/linked.pdf"


def test_hidden_and_temporary_files_are_not_inventoried(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    _write(root, "Section 15/.hidden.pdf")
    _write(root, "Section 15/~$Master Abstract.xlsx")
    _write(root, ".git/Section 15/secret.pdf")

    receipt = build_receipt(
        [SourceRoot("local", root)],
        requested_sections=[15],
    )

    assert len(receipt.files) == 3


def test_receipt_cannot_be_written_inside_source_root(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    receipt = build_receipt(
        [SourceRoot("local", root)],
        requested_sections=[15],
    )

    with pytest.raises(SourceAcquisitionError, match="outside"):
        write_receipt(receipt, root / "receipt.json")


def test_cli_writes_blocking_receipt_and_returns_two(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _write(root, "Section 15/Master Abstract.xlsx", b"master only")
    output = tmp_path / "receipts" / "source.json"

    result = main(
        [
            "--root",
            f"local={root}",
            "--section",
            "15",
            "--output",
            str(output),
        ]
    )

    assert result == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_id"] == "dbx.source_acquisition_receipt"
    assert payload["technical_pass"] is False
    assert payload["sections"][0]["missing_required_roles"] == [
        "source_document",
        "index",
    ]


def test_duplicate_root_labels_are_rejected(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    with pytest.raises(SourceAcquisitionError, match="labels must be unique"):
        build_receipt(
            [SourceRoot("drive", first), SourceRoot("drive", second)],
            requested_sections=[15],
        )


def test_overlapping_source_roots_are_rejected(tmp_path: Path) -> None:
    parent = tmp_path / "sources"
    child = parent / "drive"
    child.mkdir(parents=True)

    with pytest.raises(SourceAcquisitionError, match="must not overlap"):
        build_receipt(
            [SourceRoot("pc", parent), SourceRoot("drive", child)],
            requested_sections=[15],
        )


def test_empty_source_file_blocks_intake(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    _write(root, "Section 15/Recorded Faces/Instrument 1.pdf", b"")

    receipt = build_receipt(
        [SourceRoot("local", root)],
        requested_sections=[15],
    )

    assert not receipt.technical_pass
    assert receipt.issues[0].code == "source_empty"
    assert "source_document" in receipt.sections[0].missing_required_roles


def test_source_change_during_hash_blocks_intake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    original_sha256 = source_acquisition.sha256_file

    def mutate_after_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
        digest = original_sha256(path, chunk_size)
        if path.name == "Master Abstract.xlsx":
            path.write_bytes(b"changed after hashing")
        return digest

    monkeypatch.setattr(source_acquisition, "sha256_file", mutate_after_hash)

    receipt = build_receipt(
        [SourceRoot("local", root)],
        requested_sections=[15],
    )

    assert not receipt.technical_pass
    assert any(
        issue.code == "source_changed_during_hash"
        for issue in receipt.issues
    )
    assert "master_workbook" in receipt.sections[0].missing_required_roles


def test_abstract_checklist_is_not_accepted_as_master(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _write(root, "Section 15/Abstract Checklist.xlsx", b"checklist")
    _write(root, "Section 15/County Index.pdf", b"index")
    _write(root, "Section 15/Recorded Face.pdf", b"face")

    receipt = build_receipt(
        [SourceRoot("local", root)],
        requested_sections=[15],
    )

    assert not receipt.technical_pass
    assert receipt.sections[0].missing_required_roles == ["master_workbook"]


def test_unknown_required_role_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()

    with pytest.raises(SourceAcquisitionError, match="Required roles"):
        build_receipt(
            [SourceRoot("local", root)],
            requested_sections=[15],
            required_roles=["invented_role"],
        )
