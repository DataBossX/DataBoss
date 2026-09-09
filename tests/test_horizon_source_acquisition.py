"""Tests for read-only, fail-closed section source acquisition receipts."""

import json
import os
import stat
from dataclasses import replace
from pathlib import Path
from typing import Optional

import pytest

import horizon.source_acquisition as source_acquisition
from horizon.source_acquisition import (
    AuthorityAssertion,
    AuthorityContext,
    SourceAcquisitionError,
    SourceRoot,
    build_receipt,
    detect_section,
    main,
    verify_snapshot,
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


def _authorities(
    root: Path,
    label: str,
    section: int,
    *,
    index_name: str = "County Index.pdf",
    source_name: str = "Recorded Faces/Instrument 1.pdf",
) -> list[AuthorityAssertion]:
    paths = {
        "master_workbook": "Master Abstract.xlsx",
        "index": index_name,
        "source_document": source_name,
    }
    return [
        AuthorityAssertion(
            root_label=label,
            relative_path=f"Section {section}/{relative_path}",
            section=section,
            role=role,
            expected_sha256=source_acquisition.sha256_file(
                root / f"Section {section}" / relative_path
            ),
        )
        for role, relative_path in paths.items()
    ]


def _context() -> AuthorityContext:
    return AuthorityContext(
        project_id="DBX-TEST",
        decision_id="SOURCE-AUTH-001",
        approved_by="Synthetic Test Examiner",
        project_manifest_sha256="1" * 64,
        source_authority_sha256="2" * 64,
    )


def _write_authority_manifest(
    path: Path,
    assertions: list[AuthorityAssertion],
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_id": "dbx.source_authority_manifest",
                "schema_version": "1.0",
                "project_id": "DBX-TEST",
                "decision_id": "SOURCE-AUTH-001",
                "approved_by": "Synthetic Test Examiner",
                "authorities": [
                    {
                        "root_label": assertion.root_label,
                        "relative_path": assertion.relative_path,
                        "section": assertion.section,
                        "role": assertion.role,
                        "expected_sha256": assertion.expected_sha256,
                    }
                    for assertion in assertions
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_project_manifest(path: Path, authority_path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_id": "dbx.project_manifest",
                "schema_version": "1.1",
                "project_id": "DBX-TEST",
                "source_policy": "IMMUTABLE_READ_ONLY",
                "authority_hashes": {
                    "source_authority": source_acquisition.sha256_file(
                        authority_path
                    )
                },
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


def test_exact_pc_drive_sources_are_ready_for_extraction(tmp_path: Path) -> None:
    pc = tmp_path / "pc"
    drive = tmp_path / "drive"
    _complete_section(pc, 15)
    _complete_section(drive, 15)

    receipt = build_receipt(
        [SourceRoot("pc", pc), SourceRoot("drive", drive)],
        requested_sections=[15],
        authority_assertions=_authorities(pc, "pc", 15),
        authority_context=_context(),
        snapshot_directory=tmp_path / "snapshot",
    )

    assert receipt.technical_pass
    assert receipt.sections[0].ready_for_extraction
    assert {comparison.status for comparison in receipt.path_comparisons} == {
        "exact_match"
    }
    assert len(receipt.duplicate_content) == 3
    snapshot = Path(receipt.snapshot_root)
    assert receipt.snapshot_manifest_sha256
    assert (
        snapshot / "pc" / "Section 15" / "Master Abstract.xlsx"
    ).read_bytes() == b"master"
    assert verify_snapshot(receipt)


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
        authority_assertions=_authorities(pc, "pc", 15),
        authority_context=_context(),
        snapshot_directory=tmp_path / "snapshot",
    )

    assert not receipt.technical_pass
    assert receipt.sections[0].conflicting_paths == 1
    assert any(
        comparison.status == "hash_conflict"
        and comparison.relative_path == "Section 15/Master Abstract.xlsx"
        for comparison in receipt.path_comparisons
    )


def test_snapshot_verification_detects_post_receipt_tampering(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    receipt = build_receipt(
        [SourceRoot("pc", root)],
        requested_sections=[15],
        authority_assertions=_authorities(root, "pc", 15),
        authority_context=_context(),
        snapshot_directory=tmp_path / "snapshot",
    )
    snapshot_file = (
        Path(receipt.snapshot_root)
        / "pc"
        / "Section 15"
        / "Master Abstract.xlsx"
    )
    snapshot_file.chmod(0o600)
    snapshot_file.write_bytes(b"tampered")

    assert not verify_snapshot(receipt)


def test_missing_priority_sections_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)

    receipt = build_receipt(
        [SourceRoot("pc", root)],
        authority_assertions=_authorities(root, "pc", 15),
        authority_context=_context(),
        snapshot_directory=tmp_path / "snapshot",
    )

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
        [SourceRoot("pc", root)],
        requested_sections=[13],
        authority_assertions=[
            AuthorityAssertion(
                root_label="pc",
                relative_path=f"Section 13/{relative_path}",
                section=13,
                role=role,
                expected_sha256=source_acquisition.sha256_file(
                    root / "Section 13" / relative_path
                ),
            )
            for role, relative_path in {
                "master_workbook": "Master Abstract.xlsx",
                "handwritten_index": "Handwritten Index.tif",
                "source_document": "Recorded Face.pdf",
            }.items()
        ],
        authority_context=_context(),
        snapshot_directory=tmp_path / "snapshot",
    )

    assert receipt.technical_pass
    assert receipt.sections[0].candidate_role_counts["handwritten_index"] == 1


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
        [SourceRoot("pc", root)],
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
        [SourceRoot("pc", root)],
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
        [SourceRoot("pc", root)],
        requested_sections=[15],
    )

    assert len(receipt.files) == 3


def test_receipt_cannot_be_written_inside_source_root(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    receipt = build_receipt(
        [SourceRoot("pc", root)],
        requested_sections=[15],
    )

    with pytest.raises(SourceAcquisitionError, match="outside"):
        write_receipt(receipt, root / "receipt.json")


def test_cli_writes_blocking_receipt_and_returns_two(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _write(root, "Section 15/Master Abstract.xlsx", b"master only")
    output = tmp_path / "receipts" / "source.json"
    output.parent.mkdir()

    result = main(
        [
            "--root",
            f"pc={root}",
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
        "master_workbook",
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
        [SourceRoot("pc", root)],
        requested_sections=[15],
        authority_assertions=_authorities(root, "pc", 15),
        authority_context=_context(),
        snapshot_directory=tmp_path / "snapshot",
    )

    assert not receipt.technical_pass
    assert receipt.issues[0].code == "source_empty"
    assert "source_document" in receipt.sections[0].missing_required_roles


def test_source_change_during_hash_blocks_intake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    authority_assertions = _authorities(root, "pc", 15)
    original_hash = source_acquisition._hash_regular_file

    def mutate_after_hash(path: Path, chunk_size: int = 1024 * 1024):
        result = original_hash(path, chunk_size)
        if path.name == "Master Abstract.xlsx":
            path.write_bytes(b"changed after hashing")
        return result

    monkeypatch.setattr(
        source_acquisition,
        "_hash_regular_file",
        mutate_after_hash,
    )

    receipt = build_receipt(
        [SourceRoot("pc", root)],
        requested_sections=[15],
        authority_assertions=authority_assertions,
        authority_context=_context(),
        snapshot_directory=tmp_path / "snapshot",
    )

    assert not receipt.technical_pass
    assert any(
        issue.code == "source_tree_changed_during_scan"
        for issue in receipt.issues
    )
    assert "master_workbook" in receipt.sections[0].missing_required_roles


def test_filename_heuristics_do_not_authorize_source_roles(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _write(root, "Section 15/Abstract Checklist.xlsx", b"checklist")
    _write(root, "Section 15/County Index.pdf", b"index")
    _write(root, "Section 15/Recorded Face.pdf", b"face")

    receipt = build_receipt(
        [SourceRoot("pc", root)],
        requested_sections=[15],
    )

    assert not receipt.technical_pass
    assert receipt.sections[0].missing_required_roles == [
        "source_document",
        "master_workbook",
        "index",
    ]


def test_unknown_required_role_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()

    with pytest.raises(SourceAcquisitionError, match="Required roles"):
        build_receipt(
            [SourceRoot("pc", root)],
            requested_sections=[15],
            required_roles=["invented_role"],
        )


def test_hash_bound_authority_manifest_allows_cli_pass(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    authority_path = tmp_path / "authority.json"
    _write_authority_manifest(
        authority_path,
        _authorities(root, "pc", 15),
    )
    project_path = tmp_path / "project_manifest.json"
    _write_project_manifest(project_path, authority_path)
    output = tmp_path / "receipts" / "source.json"
    output.parent.mkdir()

    result = main(
        [
            "--root",
            f"pc={root}",
            "--section",
            "15",
            "--authority-manifest",
            str(authority_path),
            "--project-manifest",
            str(project_path),
            "--snapshot-directory",
            str(tmp_path / "snapshot"),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["technical_pass"] is True
    assert all(
        match["status"] == "matched"
        for match in payload["authority_matches"]
    )


def test_authority_hash_mismatch_blocks_intake(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    assertions = _authorities(root, "pc", 15)
    assertions[0] = replace(
        assertions[0],
        expected_sha256="0" * 64,
    )

    receipt = build_receipt(
        [SourceRoot("pc", root)],
        requested_sections=[15],
        authority_assertions=assertions,
        authority_context=_context(),
        snapshot_directory=tmp_path / "snapshot",
    )

    assert not receipt.technical_pass
    assert any(
        issue.code == "authority_hash_mismatch"
        for issue in receipt.issues
    )


def test_authority_path_traversal_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()
    assertion = AuthorityAssertion(
        root_label="pc",
        relative_path="../outside.pdf",
        section=15,
        role="source_document",
        expected_sha256="0" * 64,
    )

    with pytest.raises(SourceAcquisitionError, match="assertion is invalid"):
        build_receipt(
            [SourceRoot("pc", root)],
            requested_sections=[15],
            authority_assertions=[assertion],
            authority_context=_context(),
            snapshot_directory=tmp_path / "snapshot",
        )


def test_directory_symlink_is_reported_and_blocks_all_sections(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "linked-drive").symlink_to(outside, target_is_directory=True)

    receipt = build_receipt(
        [SourceRoot("pc", root)],
        requested_sections=[15],
        authority_assertions=_authorities(root, "pc", 15),
        authority_context=_context(),
        snapshot_directory=tmp_path / "snapshot",
    )

    assert not receipt.technical_pass
    assert receipt.issues[0].code == "source_directory_symlink_rejected"
    assert receipt.issues[0].section is None


def test_traversal_error_is_reported_and_blocks_intake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sources"
    root.mkdir()

    def failed_walk(path, *, followlinks, onerror):
        onerror(PermissionError(13, "denied", str(root / "Section 15")))
        return iter(())

    monkeypatch.setattr(source_acquisition.os, "walk", failed_walk)

    receipt = build_receipt(
        [SourceRoot("pc", root)],
        requested_sections=[15],
    )

    assert not receipt.technical_pass
    assert receipt.issues[0].code == "source_traversal_failed"
    assert receipt.sections[0].issue_count == 1


def test_predictable_temp_symlink_cannot_overwrite_source(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    receipt = build_receipt(
        [SourceRoot("pc", root)],
        requested_sections=[15],
    )
    source = root / "Section 15" / "Master Abstract.xlsx"
    original = source.read_bytes()
    output = tmp_path / "receipts" / "source.json"
    output.parent.mkdir()
    output.with_suffix(".json.tmp").symlink_to(source)

    write_receipt(receipt, output)

    assert source.read_bytes() == original
    assert output.is_file()


def test_cli_syntax_error_returns_one_without_receipt(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"

    result = main(["--root", "pc= ", "--output", str(output)])

    assert result == 1
    assert not output.exists()


def test_unknown_root_kind_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    root.mkdir()

    with pytest.raises(SourceAcquisitionError, match="pc, drive, or chat"):
        build_receipt(
            [SourceRoot("local", root)],
            requested_sections=[15],
        )


def test_relative_source_root_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SourceAcquisitionError, match="absolute"):
        build_receipt(
            [SourceRoot("pc", Path("relative"))],
            requested_sections=[15],
        )


def test_one_location_cannot_authorize_multiple_roles(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    source = root / "Section 15" / "Master Abstract.xlsx"
    digest = source_acquisition.sha256_file(source)
    assertions = [
        AuthorityAssertion(
            root_label="pc",
            relative_path="Section 15/Master Abstract.xlsx",
            section=15,
            role=role,
            expected_sha256=digest,
        )
        for role in ("master_workbook", "index")
    ]

    with pytest.raises(SourceAcquisitionError, match="must be unique"):
        build_receipt(
            [SourceRoot("pc", root)],
            requested_sections=[15],
            authority_assertions=assertions,
            authority_context=_context(),
            snapshot_directory=tmp_path / "snapshot",
        )


def test_second_full_scan_detects_added_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    assertions = _authorities(root, "pc", 15)
    original_inventory = source_acquisition.inventory_roots
    calls = 0

    def inventory_with_addition(roots, requested_sections):
        nonlocal calls
        calls += 1
        if calls == 2:
            _write(root, "Section 15/late-addition.pdf", b"late")
        return original_inventory(roots, requested_sections)

    monkeypatch.setattr(
        source_acquisition,
        "inventory_roots",
        inventory_with_addition,
    )

    receipt = build_receipt(
        [SourceRoot("pc", root)],
        requested_sections=[15],
        authority_assertions=assertions,
        authority_context=_context(),
        snapshot_directory=tmp_path / "snapshot",
    )

    assert not receipt.technical_pass
    assert any(
        issue.code == "source_tree_changed_during_scan"
        for issue in receipt.issues
    )


def test_final_rehash_detects_metadata_preserving_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    assertions = _authorities(root, "pc", 15)
    original_hash = source_acquisition._hash_regular_file
    master_hashes = 0

    def mutate_after_second_hash(
        path: Path,
        chunk_size: int = 1024 * 1024,
    ):
        nonlocal master_hashes
        result = original_hash(path, chunk_size)
        if path.name == "Master Abstract.xlsx":
            master_hashes += 1
            if master_hashes == 2:
                source_stat = result[1]
                path.write_bytes(b"change")
                path.touch()
                path.chmod(stat.S_IMODE(source_stat.st_mode))
                os.utime(
                    path,
                    ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns),
                )
        return result

    monkeypatch.setattr(
        source_acquisition,
        "_hash_regular_file",
        mutate_after_second_hash,
    )

    receipt = build_receipt(
        [SourceRoot("pc", root)],
        requested_sections=[15],
        authority_assertions=assertions,
        authority_context=_context(),
        snapshot_directory=tmp_path / "snapshot",
    )

    assert not receipt.technical_pass
    assert any(
        issue.code == "source_changed_after_hash"
        for issue in receipt.issues
    )


def test_project_manifest_hash_prevents_authority_substitution(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    authority_path = tmp_path / "authority.json"
    _write_authority_manifest(
        authority_path,
        _authorities(root, "pc", 15),
    )
    project_path = tmp_path / "project_manifest.json"
    _write_project_manifest(project_path, authority_path)
    authority_path.write_text("{}", encoding="utf-8")
    output = tmp_path / "receipt.json"

    result = main(
        [
            "--root",
            f"pc={root}",
            "--section",
            "15",
            "--authority-manifest",
            str(authority_path),
            "--project-manifest",
            str(project_path),
            "--snapshot-directory",
            str(tmp_path / "snapshot"),
            "--output",
            str(output),
        ]
    )

    assert result == 1
    assert not output.exists()


@pytest.mark.parametrize("use_symlink", [False, True])
def test_receipt_cannot_alias_authority_manifest(
    tmp_path: Path, use_symlink: bool
) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    authority_path = tmp_path / "authority.json"
    _write_authority_manifest(
        authority_path,
        _authorities(root, "pc", 15),
    )
    project_path = tmp_path / "project_manifest.json"
    _write_project_manifest(project_path, authority_path)
    original = authority_path.read_bytes()
    output = tmp_path / "receipt-link.json" if use_symlink else authority_path
    if use_symlink:
        output.symlink_to(authority_path)

    result = main(
        [
            "--root",
            f"pc={root}",
            "--section",
            "15",
            "--authority-manifest",
            str(authority_path),
            "--project-manifest",
            str(project_path),
            "--snapshot-directory",
            str(tmp_path / "snapshot"),
            "--output",
            str(output),
        ]
    )

    assert result == 1
    assert authority_path.read_bytes() == original


def test_receipt_failure_removes_private_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "sources"
    _complete_section(root, 15)
    authority_path = tmp_path / "authority.json"
    _write_authority_manifest(
        authority_path,
        _authorities(root, "pc", 15),
    )
    project_path = tmp_path / "project_manifest.json"
    _write_project_manifest(project_path, authority_path)
    output = tmp_path / "receipt.json"
    snapshot = tmp_path / "snapshot"

    def fail_receipt_write(*args, **kwargs):
        raise SourceAcquisitionError("simulated receipt failure")

    monkeypatch.setattr(
        source_acquisition,
        "write_receipt",
        fail_receipt_write,
    )

    result = main(
        [
            "--root",
            f"pc={root}",
            "--section",
            "15",
            "--authority-manifest",
            str(authority_path),
            "--project-manifest",
            str(project_path),
            "--snapshot-directory",
            str(snapshot),
            "--output",
            str(output),
        ]
    )

    assert result == 1
    assert not snapshot.exists()
