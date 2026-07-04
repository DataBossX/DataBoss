"""XML editor: safe formula edit preserves drawings/media; never overwrites."""
import zipfile
from pathlib import Path

import pytest

from repair.xml_editor import SafeXlsxEditor, XmlEditError


def test_preserves_media_and_drawings(sample_wb_media, tmp_path):
    ed = SafeXlsxEditor(sample_wb_media)
    assert "xl/media/image1.png" in ed.entry_names()
    assert "xl/drawings/drawing1.xml" in ed.entry_names()
    ed.set_full_calc_on_load()
    out = tmp_path / "edited_v001.xlsx"
    ed.save_as(out)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "xl/media/image1.png" in names
        assert "xl/drawings/drawing1.xml" in names
        # media bytes preserved unchanged
        assert z.read("xl/media/image1.png").startswith(b"\x89PNG")


def test_formula_edit_and_calcchain_removed(sample_wb, tmp_path):
    ed = SafeXlsxEditor(sample_wb)
    part = ed.sheet_part_for("Title ")
    assert part is not None
    ok = ed.set_sheet_cell_formula(part, "C10", "SUM(C8:C9)")
    assert ok is True
    out = tmp_path / "edited_v002.xlsx"
    info = ed.save_as(out)
    assert Path(out).exists()
    assert info["before_sha256"] != info["after_sha256"]
    # re-open and confirm the formula is present
    import openpyxl
    wb = openpyxl.load_workbook(out)
    assert wb["Title "]["C10"].value == "=SUM(C8:C9)"
    wb.close()


def test_refuses_overwrite(sample_wb, tmp_path):
    ed = SafeXlsxEditor(sample_wb)
    out = tmp_path / "v.xlsx"
    ed.set_full_calc_on_load()
    ed.save_as(out)
    ed2 = SafeXlsxEditor(sample_wb)
    ed2.set_full_calc_on_load()
    with pytest.raises(XmlEditError):
        ed2.save_as(out)
