"""Phases 3-9: ingestion, classification, and the domain validators."""

from __future__ import annotations

import pytest

pytest.importorskip("openpyxl")

from validation_agent.ingestion.manifest_builder import WorkbookManifestBuilder  # noqa: E402
from validation_agent.ingestion.sheet_classifier import SheetCategory  # noqa: E402
from validation_agent.models import GateStatus  # noqa: E402
from validation_agent.validators.val_acreage import AcreageValidator  # noqa: E402
from validation_agent.validators.val_chain import ChainValidator  # noqa: E402
from validation_agent.validators.val_interest import InterestValidator  # noqa: E402
from validation_agent.tests.make_fixture import (build_certifiable_workbook,  # noqa: E402
                                                 build_escalation_workbook)


def _manifest(path):
    return WorkbookManifestBuilder().build("run_test", 0, path, "deadbeef")


def test_classification_identifies_core_sheets(tmp_path):
    wb = build_certifiable_workbook(tmp_path / "clean.xlsx")
    m = _manifest(wb)
    assert m.readable
    assert len(m.by_category(SheetCategory.TRACT)) >= 10
    assert m.by_category(SheetCategory.OGL_REGISTER)
    assert m.by_category(SheetCategory.WORKING_INTEREST)
    assert m.by_category(SheetCategory.RUNSHEET)


def test_acreage_flags_hardcoded_total_as_repairable(tmp_path):
    wb = build_certifiable_workbook(tmp_path / "clean.xlsx")
    m = _manifest(wb)
    g4, g10 = AcreageValidator().execute_validation(m)
    assert g4.gate_id == 4 and g4.status is GateStatus.FAIL
    assert g10.gate_id == 10 and g10.status is GateStatus.FAIL
    # The defect must be machine-repairable (restore the SUM formula).
    repairables = [f for f in g4.findings + g10.findings if f.repairable]
    assert repairables
    assert any(f.repair_hint.get("new_formula", "").startswith("=SUM")
               for f in repairables)


def test_interest_conservation_passes_on_balanced_runsheet(tmp_path):
    wb = build_certifiable_workbook(tmp_path / "clean.xlsx")
    m = _manifest(wb)
    (g3,) = InterestValidator().execute_validation(m)
    assert g3.status is GateStatus.PASS


def test_chain_gap_escalates_and_never_repairs(tmp_path):
    wb = build_escalation_workbook(tmp_path / "esc.xlsx")
    m = _manifest(wb)
    (g5,) = ChainValidator().execute_validation(m)
    assert g5.status is GateStatus.FAIL
    gaps = [f for f in g5.findings if f.category.value == "title_chain_gap"]
    assert gaps
    assert all(not f.repairable and f.escalate for f in gaps)


def test_clean_workbook_has_continuous_chain(tmp_path):
    wb = build_certifiable_workbook(tmp_path / "clean.xlsx")
    m = _manifest(wb)
    (g5,) = ChainValidator().execute_validation(m)
    assert g5.status is GateStatus.PASS
