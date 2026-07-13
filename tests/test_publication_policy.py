"""Tests for the publication-policy gate. Uses synthetic inputs only."""

from __future__ import annotations

from pathlib import Path

from scripts import check_publication_policy as gate


def test_clean_tree_passes(tmp_path, monkeypatch):
    clean = tmp_path / "module.py"
    clean.write_text("print('synthetic demo only')\n", encoding="utf-8")
    monkeypatch.setattr(gate, "tracked_files", lambda: [clean])
    assert gate.scan() == []


def test_detects_forbidden_client_project_path(monkeypatch):
    monkeypatch.setattr(
        gate, "tracked_files", lambda: [Path("projects/OK-BECKHAM-32-11N-25W/manifest.json")]
    )
    findings = gate.scan()
    assert any("forbidden path" in item for item in findings)


def test_detects_final_workbook_path(monkeypatch):
    monkeypatch.setattr(
        gate, "tracked_files", lambda: [Path("reports/report_FINAL_VERIFIED.xlsx")]
    )
    findings = gate.scan()
    assert any("forbidden path" in item for item in findings)


def test_detects_client_identifier_content(tmp_path, monkeypatch):
    doc = tmp_path / "notes.md"
    doc.write_text("This references OK-BECKHAM-32-11N-25W directly.\n", encoding="utf-8")
    monkeypatch.setattr(gate, "tracked_files", lambda: [doc])
    findings = gate.scan()
    assert any("client project identifier" in item for item in findings)


def test_detects_cloud_drive_identifier(tmp_path, monkeypatch):
    doc = tmp_path / "sources.json"
    doc.write_text('{"folder_id": "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"}\n', encoding="utf-8")
    monkeypatch.setattr(gate, "tracked_files", lambda: [doc])
    findings = gate.scan()
    assert any("cloud drive identifier" in item for item in findings)


def test_detects_google_drive_url(tmp_path, monkeypatch):
    doc = tmp_path / "link.md"
    doc.write_text(
        "https://drive.google.com/drive/folders/ABCDEFGHIJKLMNOPQRSTUV\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "tracked_files", lambda: [doc])
    findings = gate.scan()
    assert any("Google Drive" in item for item in findings)


def test_detects_client_identifier_in_workbook_cell(tmp_path, monkeypatch):
    from openpyxl import Workbook

    path = tmp_path / "generic.xlsx"
    workbook = Workbook()
    workbook.active["A1"] = "OK-BECKHAM-32-11N-25W"
    workbook.save(path)
    workbook.close()
    monkeypatch.setattr(gate, "tracked_files", lambda: [path])
    findings = gate.scan()
    assert any("client project identifier" in item for item in findings)


def test_real_evidence_hash_flagged_but_synthetic_allowed(tmp_path, monkeypatch):
    real = tmp_path / "real.json"
    real.write_text(
        '{"reported_sha256": "a1b2c3d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff00"}\n',
        encoding="utf-8",
    )
    synthetic = tmp_path / "synthetic.json"
    synthetic.write_text(
        '{"reported_sha256": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "tracked_files", lambda: [real, synthetic])
    findings = gate.scan()
    assert any("evidence hash" in item for item in findings)
    assert all("synthetic.json" not in item for item in findings)


def test_scan_of_real_repo_tree_is_clean():
    """The actual tracked tree must satisfy the publication policy."""
    assert gate.scan() == []
