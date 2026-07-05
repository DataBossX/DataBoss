"""End-to-end and unit tests proving the engine's chain math and QA discipline.

Run: python -m pytest DataBossX_Title_Report_Engine_v3/tests/test_engine.py -v
"""

from __future__ import annotations

import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_ROOT))

from engine.chain import build_all                         # noqa: E402
from engine.ingest import load_workbook_rows               # noqa: E402
from engine.models import normalize_instrument_type        # noqa: E402
from engine.ogl_matcher import match_ogls, parse_ogl_schedule  # noqa: E402
from engine.parser import parse_runsheet_book              # noqa: E402
from engine.utils import parse_interest, InterestError     # noqa: E402
from engine.verifier import final_owner_table             # noqa: E402
from tests.make_synthetic import build_synthetic_horizon   # noqa: E402


def _load_evidence(tmp_path):
    root = build_synthetic_horizon(tmp_path / "horizon")
    book = load_workbook_rows(root / "SYNTHETIC_31-12N-24W_Runsheet.xlsx")
    return parse_runsheet_book(book), book, root


# ---- unit: exact interest math (no float) --------------------------------
def test_interest_is_exact_fraction():
    assert parse_interest("1/3") == Fraction(1, 3)
    assert parse_interest("12.5%") == Fraction(1, 8)
    assert parse_interest("0.5") == Fraction(1, 2)
    assert parse_interest("1/2 of 8/8") == Fraction(1, 2)


def test_bad_interest_raises_not_guesses():
    import pytest
    with pytest.raises(InterestError):
        parse_interest("about a half")


# ---- unit: instrument normalization --------------------------------------
def test_assignment_normalizes_to_assn_not_ogl():
    assert normalize_instrument_type("Assignment of Oil and Gas Lease") == "ASSN"
    assert normalize_instrument_type("Oil and Gas Lease") == "OGL"
    assert normalize_instrument_type("Warranty Deed") == "WD"
    assert normalize_instrument_type("something weird") == "REVIEW"


# ---- e2e: parsing ---------------------------------------------------------
def test_runsheet_parses_rows(tmp_path):
    evidence, _, _ = _load_evidence(tmp_path)
    assert len(evidence) == 5
    types = [e.instrument_type for e in evidence]
    assert "WD" in types and "OGL" in types and "ASSN" in types and "MD" in types


def test_ogl_column_never_holds_bare_bookpage(tmp_path):
    evidence, _, _ = _load_evidence(tmp_path)
    for e in evidence:
        if e.ogl_number:
            assert "/" not in e.ogl_number or e.ogl_number.upper().startswith("OGL"), e.ogl_number


# ---- e2e: chain math ------------------------------------------------------
def test_tract1_balances_and_carries_ogl(tmp_path):
    evidence, _, _ = _load_evidence(tmp_path)
    results = {r.tract: r for r in build_all(evidence)}
    t1 = results["1"]
    assert t1.balanced, t1.balance_note
    owners = {o.owner: o for o in t1.final_owners}
    # ALPHA retains 1/2, BRAVO holds 1/2 with OGL carried
    assert owners["ALPHA MINERALS LLC"].mineral_interest == "1/2"
    assert owners["BRAVO HOLDINGS LLC"].mineral_interest == "1/2"
    assert owners["BRAVO HOLDINGS LLC"].ogl_number == "OGL-1001"


def test_over_conveyance_is_flagged_not_silent(tmp_path):
    evidence, _, _ = _load_evidence(tmp_path)
    results = {r.tract: r for r in build_all(evidence)}
    t2 = results["2"]
    cats = [f.category for f in t2.flags]
    assert "over_conveyance" in cats


def test_no_negative_interest(tmp_path):
    evidence, _, _ = _load_evidence(tmp_path)
    for res in build_all(evidence):
        for o in res.final_owners:
            assert not str(o.mineral_interest).startswith("-"), o


def test_assn_does_not_move_mineral_fee(tmp_path):
    evidence, _, _ = _load_evidence(tmp_path)
    results = {r.tract: r for r in build_all(evidence)}
    # DELTA (assignee of leasehold) must NOT appear as a mineral owner
    owners = [o.owner for o in results["1"].final_owners]
    assert "DELTA ENERGY PARTNERS" not in owners
    assert "CHARLIE OPERATING CO" not in owners


# ---- e2e: OGL matching ----------------------------------------------------
def test_ogl_match_report(tmp_path):
    evidence, book, _ = _load_evidence(tmp_path)
    schedule = parse_ogl_schedule(book)
    matches = match_ogls(evidence, schedule)
    statuses = {m.status for m in matches}
    assert "matched" in statuses          # OGL-1001 chained
    assert "ogl_not_chained" in statuses  # OGL-2002 in schedule, not in runsheet
