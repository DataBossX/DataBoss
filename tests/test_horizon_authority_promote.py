"""Named examiners can promote a draft; placeholders and stale hashes cannot."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horizon.authority_draft import draft_from_roots, write_draft
from horizon.authority_promote import (
    AuthorityPromoteError,
    main,
    promote,
)
from horizon.source_acquisition import (
    bind_phase_two_controls,
    sha256_file,
)


def _section15_tree(root: Path) -> None:
    section = root / "Section 15"
    section.mkdir(parents=True)
    (section / "Master Abstract.xlsx").write_bytes(b"master-15")
    (section / "County Index.xlsx").write_bytes(b"index-15")
    (section / "Handwritten Index.tif").write_bytes(b"hand-15")
    faces = section / "Recorded Faces"
    faces.mkdir()
    (faces / "Instrument 1.pdf").write_bytes(b"%PDF-1.1 face-15")


def test_promote_writes_hash_bound_manifests(tmp_path: Path) -> None:
    root = tmp_path / "pc"
    _section15_tree(root)
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    draft = draft_from_roots([f"pc={root}"], requested_sections=[15])
    draft_path = write_draft(draft, receipts / "authority-draft.json")
    receipt = promote(
        draft_path=draft_path,
        output=receipts / "source-authority.json",
        project_manifest_output=receipts / "project_manifest.json",
        project_id="DBX-TEST",
        decision_id="SOURCE-AUTH-001",
        approved_by="Pat Examiner",
        confirm_sections=[15],
        roots=[f"pc={root}"],
    )
    assert receipt["packages_complete"] is False
    assert receipt["technical_pass"] is True
    authority = json.loads(
        (receipts / "source-authority.json").read_text(encoding="utf-8")
    )
    assert authority["schema_id"] == "dbx.source_authority_manifest"
    assert authority["approved_by"] == "Pat Examiner"
    assert {item["role"] for item in authority["authorities"]} == {
        "source_document",
        "master_workbook",
        "index",
        "handwritten_index",
    }
    project = json.loads(
        (receipts / "project_manifest.json").read_text(encoding="utf-8")
    )
    assert project["authority_hashes"]["source_authority"] == sha256_file(
        receipts / "source-authority.json"
    )
    assertions, context, snapshot = bind_phase_two_controls(
        authority_manifest=receipts / "source-authority.json",
        project_manifest=receipts / "project_manifest.json",
        snapshot_directory=receipts / "intake-snapshot",
    )
    assert context is not None
    assert context.approved_by == "Pat Examiner"
    assert snapshot == receipts / "intake-snapshot"
    assert {item.section for item in assertions} == {15}


def test_promote_rejects_placeholders_and_stale_hashes(tmp_path: Path) -> None:
    root = tmp_path / "pc"
    _section15_tree(root)
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    draft_path = write_draft(
        draft_from_roots([f"pc={root}"], requested_sections=[15]),
        receipts / "authority-draft.json",
    )
    kwargs = {
        "draft_path": draft_path,
        "output": receipts / "source-authority.json",
        "project_manifest_output": receipts / "project_manifest.json",
        "project_id": "DBX-TEST",
        "decision_id": "SOURCE-AUTH-001",
        "approved_by": "Pat Examiner",
        "confirm_sections": [15],
        "roots": [f"pc={root}"],
    }
    with pytest.raises(AuthorityPromoteError, match="named examiner"):
        promote(**{**kwargs, "approved_by": "EXAMINER_NAME"})
    with pytest.raises(AuthorityPromoteError, match="placeholder"):
        promote(**{**kwargs, "project_id": "EXAMINER_PROJECT_ID"})
    with pytest.raises(AuthorityPromoteError, match="named examiner"):
        promote(**{**kwargs, "approved_by": "Named human examiner"})
    (root / "Section 15" / "Master Abstract.xlsx").write_bytes(b"changed")
    with pytest.raises(AuthorityPromoteError, match="no longer matches"):
        promote(**kwargs)


def test_promote_refuses_incomplete_section_and_repo_output(tmp_path: Path) -> None:
    incomplete = tmp_path / "pc-incomplete"
    section = incomplete / "Section 13"
    section.mkdir(parents=True)
    (section / "County Index.xlsx").write_bytes(b"index-only")
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    incomplete_draft = write_draft(
        draft_from_roots([f"pc={incomplete}"], requested_sections=[13]),
        receipts / "incomplete-draft.json",
    )
    with pytest.raises(AuthorityPromoteError, match="missing classified"):
        promote(
            draft_path=incomplete_draft,
            output=receipts / "source-authority.json",
            project_manifest_output=receipts / "project_manifest.json",
            project_id="DBX-TEST",
            decision_id="SOURCE-AUTH-001",
            approved_by="Pat Examiner",
            confirm_sections=[13],
            roots=[f"pc={incomplete}"],
        )
    complete = tmp_path / "pc-complete"
    _section15_tree(complete)
    complete_draft = write_draft(
        draft_from_roots([f"pc={complete}"], requested_sections=[15]),
        receipts / "complete-draft.json",
    )
    repo_out = Path(__file__).resolve().parents[1] / "horizon" / "source-authority.json"
    with pytest.raises(AuthorityPromoteError, match="outside this repository"):
        promote(
            draft_path=complete_draft,
            output=repo_out,
            project_manifest_output=receipts / "project_manifest.json",
            project_id="DBX-TEST",
            decision_id="SOURCE-AUTH-001",
            approved_by="Pat Examiner",
            confirm_sections=[15],
            roots=[f"pc={complete}"],
        )


def test_cli_promotes_and_stays_incomplete(tmp_path: Path) -> None:
    root = tmp_path / "pc"
    _section15_tree(root)
    receipts = tmp_path / "private-receipts"
    receipts.mkdir()
    draft_path = write_draft(
        draft_from_roots([f"pc={root}"], requested_sections=[15]),
        receipts / "authority-draft.json",
    )
    result = main(
        [
            "--draft",
            str(draft_path),
            "--output",
            str(receipts / "source-authority.json"),
            "--project-manifest-output",
            str(receipts / "project_manifest.json"),
            "--project-id",
            "DBX-TEST",
            "--decision-id",
            "SOURCE-AUTH-001",
            "--approved-by",
            "Pat Examiner",
            "--confirm-section",
            "15",
            "--root",
            f"pc={root}",
        ]
    )
    assert result == 0
    payload = json.loads((receipts / "source-authority.json").read_text(encoding="utf-8"))
    assert payload["schema_id"] == "dbx.source_authority_manifest"
