"""P1 exit tests: sheet classification + tract parsing on the real workbook."""
from __future__ import annotations

from pathlib import Path

import pytest

from validation_agent import config
from validation_agent.ingestion.workbook_map import WorkbookMapper
from validation_agent.models import SheetKind

FIXTURE = Path(__file__).parent / "fixtures" / "workbook.xlsx"


@pytest.fixture(scope="module")
def model():
    return WorkbookMapper.load(FIXTURE)


def test_all_sheets_classified(model) -> None:
    assert len(model.kinds) == 19
    assert len(model.sheets_of(SheetKind.TRACT_GRID)) == 10
    assert len(model.sheets_of(SheetKind.OGL_REGISTER)) == 1
    assert len(model.sheets_of(SheetKind.RUNSHEET)) == 1
    assert len(model.sheets_of(SheetKind.WI)) == 2
    assert len(model.sheets_of(SheetKind.WELL)) == 1
    assert len(model.sheets_of(SheetKind.RAWDATA)) == 1


def test_tracts_parse_with_correct_acreage(model) -> None:
    tracts = model.tracts()
    assert [t.tract_no for t in tracts] == list(range(1, 11))
    for t in tracts:
        assert t.acreage == config.TRACT_ACREAGE[t.tract_no]


def test_ogl_register_reads_leases(model) -> None:
    ogl = model.ogl()
    assert ogl is not None
    leases = ogl.leases()
    assert len(leases) >= 60
    nums = [l.ogl_no for l in leases if l.ogl_no is not None]
    assert nums == sorted(nums)  # monotonically numbered register


def test_runsheet_instruments(model) -> None:
    rs = model.runsheet()
    assert rs is not None
    assert len(rs.instruments()) > 400


def test_well_api_present(model) -> None:
    wells = model.wells()
    assert wells
    apis = wells[0].api_numbers()
    assert any(config.WELL_API.replace("-", "") in a.replace("-", "") for a in apis)
