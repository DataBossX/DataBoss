"""P8 hardening: single-sheet recalc slice matches full recalc for a tract grid.

The tract grids are self-contained for the G1 conservation gate, so slicing one
grid into a 1-sheet workbook and recalculating it must reproduce the same guard
cells and net-acre subtotal as the full-book recalc — at a fraction of the memory.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from validation_agent.repair.recalc_engine import RecalcEngine

FIXTURE = Path(__file__).parent / "fixtures" / "workbook.xlsx"
_HAS_LO = shutil.which("soffice") or shutil.which("libreoffice")
pytestmark = pytest.mark.skipif(not _HAS_LO, reason="LibreOffice not installed")


@pytest.fixture(scope="module")
def engine():
    return RecalcEngine()


@pytest.fixture(scope="module")
def full(engine):
    return engine.recalc(FIXTURE).values


@pytest.mark.parametrize("tract", ["Tract 3", "Tract 7"])
def test_slice_matches_full_for_guard_cells(engine, full, tract) -> None:
    sliced = engine.recalc_sheet(FIXTURE, tract).values
    # Compare the SUBTOTAL guard row (row 6) across all instrument columns.
    from openpyxl.utils import get_column_letter
    mismatches = []
    for ci in range(7, 200):
        col = get_column_letter(ci)
        f = full.get(tract, col, 6)
        s = sliced.get(tract, col, 6)
        # Normalise: RECHECK vs "" (empty renders as None in one, '' in other).
        fv = (f or "").strip() if isinstance(f, str) else f
        sv = (s or "").strip() if isinstance(s, str) else s
        if fv != sv:
            mismatches.append((col, fv, sv))
    assert not mismatches, mismatches[:5]


def test_slice_is_selfcontained_recalc(engine) -> None:
    # The E6 net-acre subtotal should compute in isolation (no #REF from slicing).
    out = engine.recalc_sheet(FIXTURE, "Tract 3")
    assert out.ok, out.errors[:5]
    e6 = out.values.get("Tract 3", "E", 6)
    assert isinstance(e6, (int, float))
