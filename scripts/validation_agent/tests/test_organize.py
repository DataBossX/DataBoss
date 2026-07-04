"""Tests for the workspace organizer: extraction, dedupe, trash, zip-slip."""

from __future__ import annotations

import zipfile

import pytest

from validation_agent.tools.organize_workspace import WorkspaceOrganizer


def _make_messy(root):
    (root / "sub").mkdir()
    (root / "a.txt").write_text("hello world", encoding="utf-8")
    (root / "sub" / "a_copy.txt").write_text("hello world", encoding="utf-8")  # dup
    (root / "unique.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    (root / "Thumbs.db").write_bytes(b"junk")
    (root / "empty.tmp").write_bytes(b"")
    with zipfile.ZipFile(root / "bundle.zip", "w") as z:
        z.writestr("inside.txt", "zipped content")
    return root


def test_extract_dedupe_trash(tmp_path):
    _make_messy(tmp_path)
    result = WorkspaceOrganizer().run(tmp_path)
    assert len(result.extracted_zips) == 1
    # inside.txt should now exist on disk (extracted).
    assert (tmp_path / "bundle" / "inside.txt").is_file()
    # one duplicate quarantined, not deleted.
    assert len(result.duplicates) == 1
    assert (tmp_path / "_quarantine" / "duplicates").exists()
    # junk + empty file quarantined.
    assert len(result.trash) == 2
    # inventory report written.
    assert (tmp_path / "_quarantine" / "inventory.json").is_file()


def test_workbooks_discovered(tmp_path):
    pytest.importorskip("openpyxl")
    from validation_agent.tests.make_fixture import build_certifiable_workbook
    build_certifiable_workbook(tmp_path / "prospect.xlsx")
    result = WorkspaceOrganizer().run(tmp_path)
    assert any(w.endswith("prospect.xlsx") for w in result.workbooks)


def test_report_only_moves_nothing(tmp_path):
    _make_messy(tmp_path)
    result = WorkspaceOrganizer(quarantine=False).run(tmp_path)
    assert len(result.duplicates) == 1  # still reported
    # originals remain in place; nothing moved to quarantine.
    assert (tmp_path / "sub" / "a_copy.txt").is_file()


def test_zip_slip_is_refused(tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../escaped.txt", "pwned")
    with pytest.raises(RuntimeError):
        WorkspaceOrganizer._safe_extract(evil, tmp_path / "dest")
    # the traversal target must not have been created outside dest.
    assert not (tmp_path / "escaped.txt").exists()
