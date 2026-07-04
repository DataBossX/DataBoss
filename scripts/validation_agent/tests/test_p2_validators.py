"""P2 exit tests: gates produce the expected verdict on the real workbook.

Numeric gates (G1/G2/G3) require *recalculated* values — the delivered workbook
carries fullCalcOnLoad and no calcChain, so its stored cache is intentionally
stale. We therefore feed a LibreOffice recalc pass (module-scoped, ~90s).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from validation_agent.ingestion.workbook_map import WorkbookMapper
from validation_agent.models import GateId, Severity
from validation_agent.repair.recalc_engine import RecalcEngine
from validation_agent.validation import default_suite

FIXTURE = Path(__file__).parent / "fixtures" / "workbook.xlsx"

_HAS_LO = shutil.which("soffice") or shutil.which("libreoffice")
pytestmark = pytest.mark.skipif(not _HAS_LO, reason="LibreOffice not installed")


@pytest.fixture(scope="module")
def model():
    return WorkbookMapper.load(FIXTURE)


@pytest.fixture(scope="module")
def recalc_values():
    return RecalcEngine().recalc(FIXTURE).values


def test_suite_runs_all_five_gates(model, recalc_values) -> None:
    results, sc = default_suite().run_all(model, recalc_values)
    assert set(sc.scores) == set(GateId)


def test_g2_footing_passes_under_recalc(model, recalc_values) -> None:
    _, sc = default_suite().run_all(model, recalc_values)
    assert sc.scores[GateId.G2_FOOTING].passed


def test_g1_flags_only_known_arti_columns_as_warn(model, recalc_values) -> None:
    results, sc = default_suite().run_all(model, recalc_values)
    g1 = [r for r in results if r.gate == GateId.G1_CONSERVATION and not r.passed]
    # Known unresolved ARTI/interest columns (guard RECHECK): a small, bounded set.
    assert 1 <= len(g1) <= 12
    # None are FAIL (they escalate as WARN, never auto-invented).
    assert all(r.severity == Severity.WARN for r in g1)


def test_g3_orphans_are_warn_not_fail(model, recalc_values) -> None:
    results, _ = default_suite().run_all(model, recalc_values)
    g3 = [r for r in results if r.gate == GateId.G3_CHAIN and not r.passed]
    assert all(r.severity == Severity.WARN for r in g3)


def test_g4_coverage_metric_present(model, recalc_values) -> None:
    results, _ = default_suite().run_all(model, recalc_values)
    g4 = [r for r in results if r.gate == GateId.G4_INSTRUMENT and r.metric is not None]
    assert g4 and 0.0 <= g4[0].metric <= 1.0


def test_g5_register_has_no_fail_after_normalization(model, recalc_values) -> None:
    _, sc = default_suite().run_all(model, recalc_values)
    # Duplicate-number / non-bijection would be FAIL; phantom refs are WARN.
    assert sc.scores[GateId.G5_OGL].worst != Severity.FAIL
