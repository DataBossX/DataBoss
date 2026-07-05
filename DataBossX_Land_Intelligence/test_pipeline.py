"""Deterministic tests for the Land Intelligence core.

These exercise the parts that must never regress: the Decimal verifier, the
chaining engine's OGL carry / ASSN handling, and the self-healing loop's
assumption behaviour. They run without an LLM (deterministic path only).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from chaining import chain_tract, classify
from schemas import OwnerInterest, RunsheetInstrument, looks_like_book_page, quantize_acres
from tasks import run_pipeline
from verifier import verify_tract

HERE = Path(__file__).parent
SAMPLE = HERE / "data" / "input" / "sample_runsheet.xlsx"
TEMPLATE = HERE / "data" / "template" / "template.xlsx"


def _owner(name, acres, ogl=None):
    return OwnerInterest(owner=name, acres=Decimal(str(acres)), ogl=ogl)


# --- verifier --------------------------------------------------------------


def test_verifier_balances_exactly():
    owners = [_owner("A", "80"), _owner("B", "80")]
    res = verify_tract(owners, Decimal("160"), tract="1")
    assert res.passed
    assert res.delta == Decimal("0.000000")


def test_verifier_detects_shortfall():
    owners = [_owner("A", "80")]
    res = verify_tract(owners, Decimal("160"), tract="1")
    assert not res.passed
    assert res.delta == Decimal("-80.000000")
    assert "UNBALANCED" in " ".join(res.errors)


def test_verifier_rejects_negative():
    with pytest.raises(Exception):
        _owner("A", "-5")  # schema ge=0 blocks negative acreage


def test_tolerance_is_micro_acre():
    owners = [_owner("A", "159.9999995")]  # within 0.000001 of 160? no -> off by 0.0000005
    res = verify_tract(owners, Decimal("160"), tract="1")
    # 160 - 159.999999(5 rounds to 160.000000) -> within tolerance
    assert res.delta == Decimal("0.000000")
    assert res.passed


# --- schema guards ---------------------------------------------------------


def test_ogl_field_rejects_book_page():
    assert looks_like_book_page("1330/410")
    assert looks_like_book_page("Bk 1330 Pg 410")
    assert not looks_like_book_page("OGL-207")
    inst = RunsheetInstrument(row=0, tract="1", ogl_ref="1330/410")
    assert inst.ogl_ref is None  # book/page never survives into an OGL field


def test_assignment_normalizes_to_ASSN():
    assert classify("Assignment") == "ASSN"
    assert classify("ASSN") == "ASSN"
    assert classify("OGL") == "LEASE"
    assert classify("WD") == "MOVE"


# --- chaining --------------------------------------------------------------


def test_ogl_carries_beside_leased_owners():
    insts = [
        RunsheetInstrument(row=0, tract="1", conveyance="MD", grantor="STATE",
                           grantee="HOLLIS", gross_acres="160", date="01/10/2018"),
        RunsheetInstrument(row=1, tract="1", conveyance="OGL", grantor="HOLLIS",
                           grantee="OP", ogl_ref="OGL-101", date="03/05/2019"),
        RunsheetInstrument(row=2, tract="1", conveyance="WD", grantor="HOLLIS",
                           grantee="CALLAHAN", gross_acres="80", date="06/12/2020"),
    ]
    result, _ = chain_tract("1", insts, Decimal("160"))
    by_name = {o.owner: o for o in result.final_owners}
    assert by_name["HOLLIS"].acres == Decimal("80.000000")
    assert by_name["CALLAHAN"].acres == Decimal("80.000000")
    # OGL-101 carried down beside BOTH leased owners (the Tract 1 pattern).
    assert by_name["HOLLIS"].ogl == "OGL-101"
    assert by_name["CALLAHAN"].ogl == "OGL-101"


def test_missing_ogl_is_flagged_not_faked():
    insts = [
        RunsheetInstrument(row=0, tract="9", conveyance="MD", grantor="STATE",
                           grantee="W", gross_acres="160", date="01/01/2016"),
        RunsheetInstrument(row=1, tract="9", conveyance="OGL", grantor="W",
                           grantee="OP", ogl_ref="", bk_pg="1291/022", date="02/02/2019"),
    ]
    result, _ = chain_tract("9", insts, Decimal("160"))
    w = result.final_owners[0]
    assert w.ogl is None  # never fabricated
    assert w.is_assumption  # flagged for examiner review
    assert result.review_flags


def test_no_owner_conveys_more_than_owned():
    insts = [
        RunsheetInstrument(row=0, tract="5", conveyance="MD", grantor="STATE",
                           grantee="X", gross_acres="160", date="01/01/2015"),
        RunsheetInstrument(row=1, tract="5", conveyance="WD", grantor="X",
                           grantee="Y", gross_acres="200", date="02/02/2016"),
    ]
    result, conveyances = chain_tract("5", insts, Decimal("160"))
    # Over-conveyance is capped so nobody goes negative, and the tract still
    # totals to its acreage.
    assert all(o.acres >= 0 for o in result.final_owners)
    assert result.total_acres == Decimal("160.000000")


# --- end to end ------------------------------------------------------------


@pytest.mark.skipif(not SAMPLE.exists() or not TEMPLATE.exists(),
                    reason="sample/template not generated")
def test_end_to_end_pipeline_balances():
    outcome = run_pipeline(SAMPLE, tract_acres_map={"1": 160, "2": 160, "3": 160},
                           use_llm=False)
    assert outcome["summary"]["tracts_processed"] == 3
    for res in outcome["results"].values():
        # Every tract totals exactly to its acreage (rule 13).
        assert res.total_acres == quantize_acres(res.tract_acres)
