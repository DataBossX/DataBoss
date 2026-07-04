"""Tests for the Golden-Source validation gate and pydantic models."""

from horizon.models import ReportModel, TitleRow
from horizon.validation import Requirements, validate_report


def _report(rows):
    return ReportModel(section="31-12N-24W", rows=rows)


def test_clean_report_passes():
    rows = [
        TitleRow(grantor="A", grantee="B", instrument_number="100",
                 conveyed_interest="1/2", retained_interest="1/2"),
    ]
    vr = validate_report(_report(rows), Requirements())
    assert vr.passed
    assert not vr.errors


def test_impossible_implied_holding_is_error():
    rows = [
        TitleRow(grantor="A", grantee="B", instrument_number="100",
                 conveyed_interest="3/4", retained_interest="1/2"),  # implies 5/4 held
    ]
    # conveyed 3/4 + retained 1/2 = 5/4 implies the grantor held more than the
    # full 8/8 estate, which is impossible -> the gate must flag it as an error.
    vr = validate_report(_report(rows), Requirements())
    assert not vr.passed
    assert any(i.severity == "error" and "8/8 estate" in i.message for i in vr.errors)


def test_valid_split_passes():
    rows = [
        TitleRow(grantor="A", grantee="B", instrument_number="100",
                 conveyed_interest="1/4", retained_interest="1/2"),  # implies 3/4 held
    ]
    assert validate_report(_report(rows), Requirements()).passed


def test_escalated_row_is_flagged_not_failed():
    rows = [TitleRow(grantor="A", grantee="B", instrument_number="1",
                     remarks="ESCALATED: HBP fact unsupported")]
    vr = validate_report(_report(rows), Requirements())
    assert any(i.severity == "escalated" for i in vr.issues)
    assert vr.passed  # escalations are surfaced, they don't crash the gate


def test_review_row_flagged():
    rows = [TitleRow(grantor="A", grantee="B", instrument_number="1",
                     status="Needs Examiner Review")]
    vr = validate_report(_report(rows), Requirements())
    assert any(i.severity == "review" for i in vr.issues)


def test_missing_required_instrument_is_error():
    rows = [TitleRow(grantor="A", grantee="B", instrument_number="100")]
    reqs = Requirements(required_instruments={"100", "200"})
    vr = validate_report(_report(rows), reqs)
    assert not vr.passed
    assert any("200" in i.message for i in vr.errors)


def test_missing_instrument_number_warns():
    rows = [TitleRow(grantor="A", grantee="B", instrument_number="")]
    vr = validate_report(_report(rows), Requirements())
    assert any(i.severity == "warn" and i.field == "instrument_number"
               for i in vr.issues)
    assert vr.passed  # warn does not fail the gate


def test_titlerow_needs_review_property():
    r = TitleRow(remarks="something Needs Examiner Review here")
    assert r.needs_review
