"""Unapproved Phase 1 drafts are not legal authority."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horizon.authority_draft import (
    DRAFT_SCHEMA_ID,
    UNAPPROVED_STATUS,
    AuthorityDraftError,
    draft_from_files,
    draft_from_roots,
    main,
    write_draft,
)
from horizon.source_acquisition import (
    SourceAcquisitionError,
    SourceFile,
    bind_phase_two_controls,
    load_authority_manifest,
    sha256_file,
)


def _file(
    *,
    section: int,
    role: str,
    relative_path: str,
    digest: str,
    root_label: str = "pc",
) -> SourceFile:
    return SourceFile(
        root_label=root_label,
        relative_path=relative_path,
        section=section,
        candidate_role=role,
        extension=Path(relative_path).suffix.casefold(),
        size_bytes=8,
        modified_utc="2026-09-14T00:00:00+00:00",
        modified_ns=0,
        device=0,
        inode=0,
        sha256=digest,
    )


def _section15_files() -> list[SourceFile]:
    return [
        _file(
            section=15,
            role="source_document",
            relative_path="Section 15/Recorded Faces/Instrument 1.pdf",
            digest="a" * 64,
        ),
        _file(
            section=15,
            role="master_workbook",
            relative_path="Section 15/Master Abstract.xlsx",
            digest="b" * 64,
        ),
        _file(
            section=15,
            role="index",
            relative_path="Section 15/County Index.xlsx",
            digest="c" * 64,
        ),
        _file(
            section=15,
            role="handwritten_index",
            relative_path="Section 15/Handwritten Index.xlsx",
            digest="d" * 64,
        ),
    ]


def test_draft_from_classified_section_15_is_unapproved() -> None:
    draft = draft_from_files(_section15_files(), requested_sections=[15])
    assert draft["schema_id"] == DRAFT_SCHEMA_ID
    assert draft["status"] == UNAPPROVED_STATUS
    assert draft["project_id"] == ""
    assert draft["decision_id"] == ""
    assert draft["approved_by"] == ""
    roles = {item["role"]: item for item in draft["authorities"]}
    assert set(roles) == {
        "source_document",
        "master_workbook",
        "index",
        "handwritten_index",
    }
    assert roles["index"]["relative_path"] == "Section 15/County Index.xlsx"
    assert roles["index"]["expected_sha256"] == "c" * 64
    assert roles["handwritten_index"]["relative_path"] == (
        "Section 15/Handwritten Index.xlsx"
    )
    assert any("not legal authority" in note for note in draft["notes"])


def test_draft_picks_first_sorted_path_and_notes_missing_roles() -> None:
    files = [
        _file(
            section=15,
            role="index",
            relative_path="Section 15/Z Index.xlsx",
            digest="f" * 64,
        ),
        _file(
            section=15,
            role="index",
            relative_path="Section 15/A Index.xlsx",
            digest="e" * 64,
        ),
    ]
    draft = draft_from_files(files, requested_sections=[15])
    index = next(item for item in draft["authorities"] if item["role"] == "index")
    assert index["relative_path"] == "Section 15/A Index.xlsx"
    assert any("2 classified" in note for note in draft["notes"])
    assert any("missing classified source_document" in note for note in draft["notes"])
    assert any("missing classified master_workbook" in note for note in draft["notes"])
    assert any("missing classified handwritten_index" in note for note in draft["notes"])


def test_cli_writes_draft_and_exits_incomplete(tmp_path: Path) -> None:
    root = tmp_path / "pc"
    section = root / "Section 15"
    section.mkdir(parents=True)
    (section / "Master Abstract.xlsx").write_bytes(b"master")
    (section / "County Index.xlsx").write_bytes(b"index")
    (section / "Recorded Faces").mkdir()
    (section / "Recorded Faces" / "Instrument 1.pdf").write_bytes(b"%PDF-1.1")
    output = tmp_path / "authority-draft.json"
    result = main(
        [
            "--output",
            str(output),
            "--root",
            f"pc={root}",
            "--section",
            "15",
        ]
    )
    assert result == 2
    draft = json.loads(output.read_text(encoding="utf-8"))
    assert draft["status"] == UNAPPROVED_STATUS
    assert draft["approved_by"] == ""
    assert len(draft["authorities"]) == 3
    assert any("missing classified handwritten_index" in note for note in draft["notes"])


def test_cli_requires_a_root(tmp_path: Path) -> None:
    result = main(["--output", str(tmp_path / "draft.json")])
    assert result == 1
    assert not (tmp_path / "draft.json").exists()


def test_phase2_rejects_unapproved_draft(tmp_path: Path) -> None:
    draft = draft_from_files(_section15_files(), requested_sections=[15])
    draft_path = write_draft(draft, tmp_path / "authority-draft.json")
    digest = sha256_file(draft_path)
    with pytest.raises(SourceAcquisitionError, match="UNAPPROVED_DRAFT"):
        load_authority_manifest(draft_path, expected_sha256=digest)
    project = tmp_path / "project_manifest.json"
    project.write_text(
        json.dumps(
            {
                "schema_id": "dbx.project_manifest",
                "schema_version": "1.1",
                "project_id": "DBX-TEST",
                "source_policy": "IMMUTABLE_READ_ONLY",
                "authority_hashes": {"source_authority": digest},
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
    with pytest.raises(SourceAcquisitionError, match="UNAPPROVED_DRAFT"):
        bind_phase_two_controls(
            authority_manifest=draft_path,
            project_manifest=project,
            snapshot_directory=tmp_path / "snapshot",
        )


def test_draft_from_missing_roots_fails_closed() -> None:
    with pytest.raises(AuthorityDraftError):
        draft_from_roots(["pc=/does/not/exist-section-draft"])
