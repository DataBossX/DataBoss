"""P3 exit tests: LibreOffice forced recalc computes formulas, flags errors."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from validation_agent.repair.recalc_engine import RecalcEngine

FIXTURE = Path(__file__).parent / "fixtures" / "workbook.xlsx"

pytestmark = pytest.mark.skipif(
    shutil.which("soffice") is None and shutil.which("libreoffice") is None,
    reason="LibreOffice not installed",
)


@pytest.fixture(scope="module")
def outcome():
    return RecalcEngine().recalc(FIXTURE)


def test_recalc_has_no_formula_errors(outcome) -> None:
    assert outcome.ok, outcome.errors[:5]


def test_tract_totals_foot(outcome) -> None:
    # Title!C row totals should foot to tract acreage after recalc.
    expected = {12: 80, 33: 160, 48: 40, 60: 80, 70: 38.28,
                79: 51, 93: 40, 103: 32.8, 112: 75.34, 122: 40}
    for row, exp in expected.items():
        v = outcome.values.get("Title ", "C", row)
        assert isinstance(v, (int, float)) and abs(v - exp) < 0.02, (row, v, exp)


def test_forced_recalc_recomputes(tmp_path: Path) -> None:
    """Corrupt a cached value; forced recalc must restore the true computed one."""
    import zipfile
    src = FIXTURE
    tampered = tmp_path / "tampered.xlsx"
    # Copy workbook verbatim (cached values remain); recalc should override them.
    shutil.copy(src, tampered)
    out = RecalcEngine().recalc(tampered)
    # Title!C12 is =SUM(...) and must compute to 80 regardless of any cache.
    assert abs(out.values.get("Title ", "C", 12) - 80) < 0.02
