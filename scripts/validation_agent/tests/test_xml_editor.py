from pathlib import Path
import zipfile
from repair.xml_editor import apply_formula_edits, verify_workbook

def test_preserves_media_and_applies_formula(sample_workbook, tmp_path):
    out = tmp_path/"repaired_v001.xlsx"
    res = apply_formula_edits(sample_workbook, out, [
        {"sheet":"Tract 1","cell":"B4","new_formula":"=A2*A3"}])
    assert res["verify"]["valid"] is True
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "xl/media/image1.png" in names          # media preserved
        assert "xl/drawings/drawing1.xml" in names       # drawing preserved
        assert "xl/calcChain.xml" not in names           # calcChain removed
        wbxml = z.read("xl/workbook.xml").decode()
        assert "fullCalcOnLoad" in wbxml

def test_refuses_overwrite(sample_workbook, tmp_path):
    out = tmp_path/"x_v001.xlsx"; out.write_bytes(b"exists")
    import pytest
    with pytest.raises(FileExistsError):
        apply_formula_edits(sample_workbook, out, [{"sheet":"Tract 1","cell":"B4","new_formula":"=1"}])
