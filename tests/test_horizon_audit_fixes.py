"""Regression tests for the proactive self-audit findings."""

from fractions import Fraction

import pytest

from horizon.chaining import OGLRecord, _legal_ties, reconcile_chain
from horizon.interest import InterestError, parse_interest, try_parse_interest
from horizon.models import ReportModel, TitleRow
from horizon.pipeline import chain_to_report
from horizon.validation import Requirements, validate_report


# -- #1 malformed percent must not crash the build -------------------------
@pytest.mark.parametrize("bad", ["1.2.3%", "..%", ".%", "1..2%"])
def test_malformed_percent_raises_interest_error(bad):
    with pytest.raises(InterestError):
        parse_interest(bad)
    assert try_parse_interest(bad) is None   # no uncaught ArithmeticError


def test_bad_percent_cell_does_not_abort_build():
    # a single OCR-garbled interest cell should tag the row, not crash
    ogl = [OGLRecord(instrument_number="1", grantor="A", grantee="B",
                     conveyed_interest="1.2.3%", legal_description="Sec 31")]
    build = chain_to_report(ogl, [])
    assert len(build.report.rows) == 1  # build completed
    assert build.report.rows[0].conveyed_interest == ""  # unparseable -> blank


def test_valid_percent_still_parses():
    assert parse_interest("12.5%") == Fraction(1, 8)


# -- #2 legal tie must respect token boundaries ----------------------------
@pytest.mark.parametrize("a,b,expected", [
    ("NE/4 Sec 3", "NE/4 Sec 31", False),   # 3 must NOT tie to 31
    ("Lot 1", "Lot 10", False),
    ("NE/4 Sec 31", "NE/4 Sec 31-12N-24W", True),   # genuine refinement ties
    ("", "NE/4 Sec 31", True),              # empty inherits tract
])
def test_legal_ties_token_boundary(a, b, expected):
    assert _legal_ties(a, b) is expected


def test_chain_sec3_not_accepted_into_sec31():
    records = [OGLRecord(instrument_number="1", grantor="ROOT", grantee="X",
                         conveyed_interest="1/2", legal_description="NE/4 Sec 3")]
    result = reconcile_chain("T", records, starting_interest=Fraction(1),
                             tract_legal="NE/4 Sec 31")
    assert result.needs_examiner_review
    assert not result.links[0].tied_to_legal


# -- #3 validation catches an impossible implied grantor holding -----------
def test_impossible_implied_holding_is_error():
    # conveyed 1/2 + retained 7/8 = 11/8 > full estate -> must be an error
    report = ReportModel(section="X", rows=[
        TitleRow(grantor="A", grantee="B", instrument_number="1",
                 conveyed_interest="1/2", retained_interest="7/8")])
    vr = validate_report(report, Requirements())
    assert not vr.passed
    assert any(i.severity == "error" and "8/8 estate" in i.message
               for i in vr.errors)


def test_normal_holding_still_passes():
    report = ReportModel(section="X", rows=[
        TitleRow(grantor="A", grantee="B", instrument_number="1",
                 conveyed_interest="1/2", retained_interest="1/2")])
    vr = validate_report(report, Requirements())
    assert vr.passed
