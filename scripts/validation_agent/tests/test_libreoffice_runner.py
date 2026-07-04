"""LibreOffice runner: missing dependency escalates cleanly, never pretends."""

from __future__ import annotations

from pathlib import Path

from recalc.libreoffice_runner import LibreOfficeRunner, detect_libreoffice


def test_missing_libreoffice_reports_dependency_failure(tmp_path):
    runner = LibreOfficeRunner(soffice_path=Path("/nonexistent/soffice"))
    # force unavailable
    runner.soffice_path = None
    src = tmp_path / "wb.xlsx"
    src.write_bytes(b"PK\x03\x04 fake")
    result = runner.recalculate(src, tmp_path / "wb_v001.xlsx")
    assert result.ok is False
    assert result.dependency_missing is True
    assert result.output_path is None
    assert "not found" in result.detail.lower()


def test_detect_returns_none_for_bad_path():
    assert detect_libreoffice(Path("/definitely/not/here/soffice")) in (
        None,
        # environments with a real soffice on PATH may still find it
        detect_libreoffice(None),
    )


def test_refuses_to_overwrite_existing(tmp_path):
    # Only meaningful when LibreOffice exists; otherwise dependency_missing path.
    runner = LibreOfficeRunner()
    src = tmp_path / "wb.xlsx"
    src.write_bytes(b"PK\x03\x04 fake")
    dest = tmp_path / "wb_v001.xlsx"
    dest.write_bytes(b"exists")
    result = runner.recalculate(src, dest)
    assert result.ok is False
