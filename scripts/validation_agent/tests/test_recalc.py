"""LibreOffice recalc: a missing dependency escalates cleanly (no fake success)
and the runner never overwrites an existing version file."""

from recalc import libreoffice_runner as lo
from tests.fixtures.make_fixtures import make_basic_workbook


def test_missing_libreoffice_escalates_cleanly(tmp_path, monkeypatch):
    monkeypatch.setattr(lo, "detect_libreoffice", lambda *a, **k: None)
    src = make_basic_workbook(tmp_path / "wb.xlsx")
    res = lo.recalculate(src, tmp_path / "out.xlsx")
    assert res.ok is False
    assert res.available is False
    assert "not found" in res.error.lower()
    assert res.output_path is None
    assert not (tmp_path / "out.xlsx").exists()   # no fake output


def test_recalc_refuses_to_overwrite(tmp_path, monkeypatch):
    # Even with a "present" LibreOffice, an existing dest is never clobbered.
    monkeypatch.setattr(lo, "detect_libreoffice",
                        lambda *a, **k: "/usr/bin/soffice")
    src = make_basic_workbook(tmp_path / "wb.xlsx")
    dest = tmp_path / "out.xlsx"
    dest.write_text("existing good version")
    res = lo.recalculate(src, dest)
    assert res.ok is False
    assert "overwrite" in res.error.lower()
    assert dest.read_text() == "existing good version"
