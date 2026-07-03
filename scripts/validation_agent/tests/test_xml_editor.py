"""XML editor: preserves drawings/media and unrelated entries, applies a safe
formula edit, removes calcChain, and never overwrites an existing version."""

import zipfile

import pytest

from repair.xml_editor import XMLWorkbookEditor
from tests.fixtures.make_fixtures import make_basic_workbook, inject_media


def test_preserves_drawings_and_media(tmp_path):
    src = make_basic_workbook(tmp_path / "wb.xlsx", with_hardcoded_total=True)
    inject_media(src)
    dest = tmp_path / "wb_v001.xlsx"
    with XMLWorkbookEditor(src) as ed:
        ed.set_cell_formula("Tracts", "C13", "=SUM(C2:C11)")
        report = ed.save_as(dest)
    assert report["verified"]
    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
        assert "xl/drawings/drawing1.xml" in names
        assert "xl/media/image1.png" in names
        assert zf.read("xl/media/image1.png").endswith(b"-FAKE-FIXTURE-IMAGE")


def test_formula_written_and_calcchain_removed(tmp_path):
    src = make_basic_workbook(tmp_path / "wb.xlsx", with_hardcoded_total=True)
    dest = tmp_path / "wb_v001.xlsx"
    with XMLWorkbookEditor(src) as ed:
        ed.set_cell_formula("Tracts", "C13", "=SUM(C2:C11)")
        report = ed.save_as(dest)
    assert report["verified"]
    with zipfile.ZipFile(dest) as zf:
        assert "xl/calcChain.xml" not in zf.namelist()
        sheet = zf.read("xl/worksheets/sheet1.xml").decode()
        assert "SUM(C2:C11)" in sheet


def test_refuses_to_overwrite(tmp_path):
    src = make_basic_workbook(tmp_path / "wb.xlsx", with_hardcoded_total=True)
    dest = tmp_path / "wb_v001.xlsx"
    dest.write_text("already here")
    with XMLWorkbookEditor(src) as ed:
        ed.set_cell_formula("Tracts", "C13", "=SUM(C2:C11)")
        with pytest.raises(FileExistsError):
            ed.save_as(dest)


def test_refuses_to_invent_missing_cell(tmp_path):
    src = make_basic_workbook(tmp_path / "wb.xlsx")
    with XMLWorkbookEditor(src) as ed:
        with pytest.raises(Exception):
            ed.set_cell_formula("Tracts", "ZZ999", "=1+1")
