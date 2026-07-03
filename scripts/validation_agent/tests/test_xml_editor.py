"""Phase 11: the XML editor injects a formula and preserves the package."""

from __future__ import annotations

import zipfile

import pytest

pytest.importorskip("openpyxl")
pytest.importorskip("lxml")

from validation_agent.ingestion.manifest_builder import WorkbookManifestBuilder  # noqa: E402
from validation_agent.models import CellRef, RepairAction  # noqa: E402
from validation_agent.repair.xml_editor import XMLWorkbookEditor  # noqa: E402
from validation_agent.tests.make_fixture import build_certifiable_workbook  # noqa: E402


def test_formula_injected_and_calcchain_stripped(tmp_path):
    src = build_certifiable_workbook(tmp_path / "clean.xlsx")
    dest = tmp_path / "repaired.xlsx"

    action = RepairAction(
        finding_gate_id=10,
        location=CellRef(sheet="Tract Summary", cell="B12"),
        action_type="restore_formula", old_value="600.0",
        new_formula="=SUM(B2:B11)", rationale="restore footing")

    before_names = set(zipfile.ZipFile(src).namelist())
    result = XMLWorkbookEditor().apply_repairs(src, dest, [action])
    assert result.ok, result.error
    assert result.applied

    # calcChain removed, everything else preserved.
    after_names = set(zipfile.ZipFile(dest).namelist())
    assert "xl/calcChain.xml" not in after_names
    assert before_names - {"xl/calcChain.xml"} <= after_names

    # The target cell now carries the formula (read via openpyxl, formula view).
    from openpyxl import load_workbook
    wb = load_workbook(dest, data_only=False)
    assert wb["Tract Summary"]["B12"].value == "=SUM(B2:B11)"
    wb.close()


def test_manifest_sees_restored_formula(tmp_path):
    src = build_certifiable_workbook(tmp_path / "clean.xlsx")
    dest = tmp_path / "repaired.xlsx"
    action = RepairAction(
        finding_gate_id=10, location=CellRef(sheet="Tract Summary", cell="B12"),
        action_type="restore_formula", old_value="600.0",
        new_formula="=SUM(B2:B11)", rationale="restore footing")
    XMLWorkbookEditor().apply_repairs(src, dest, [action])

    m = WorkbookManifestBuilder().build("r", 1, dest, "sha")
    summary = m.get_sheet("Tract Summary")
    assert summary.cell("B12").formula == "=SUM(B2:B11)"
