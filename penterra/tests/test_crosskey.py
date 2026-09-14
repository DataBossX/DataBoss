"""Tests for the Book/Page cross-key corrector.

Every fixture below is a REAL case face-proved from the Campbell tract-index
renders on 2026-09-14, corroborated against the Section 13 county workbook.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from tools.crosskey import (  # noqa: E402
    OracleRow, Suspect, audit, digit_distance, suggest,
)

# Verified rows from the Section 13 county workbook (332 rows / 332 unique / 0 dupes).
ORACLE = [
    OracleRow("500112", "0569-0288", "8/12/1981", "3/27/1981",
              "First Amendment of Unit Agreement", "Cities Service Co.", "The Public"),
    OracleRow("500113", "0569-0292", "8/12/1981", "3/27/1981",
              "Second Amendment of Unit Agreement", "Cities Service Co. et al", "The Public"),
    OracleRow("500114", "0569-0298", "8/12/1981", "5/14/1981",
              "Third Amendment of Unit Agreement", "Cities Service Co.", "The Public"),
    OracleRow("522831", "0654-0561", "12/31/1982", "12/27/1982",
              "Warranty Deed", "Charles M. Christensen et ux", "Janet Kay Christensen"),
    OracleRow("522832", "0654-0568", "12/31/1982", "12/27/1982",
              "Warranty Deed", "Charles M. Christensen et ux", "Robert Frederick Christensen"),
    OracleRow("548300", "0754-0001", "6/13/1984", "5/15/1984",
              "Release of Lien", "Republic Bank Dallas, N.A. Trustee", "Western Gas Processors, Ltd."),
    OracleRow("548301", "0754-0004", "6/13/1984", "5/15/1984",
              "Mortgage and Security Agreement", "Western Gas Processors, Ltd.", "Republic Bank Dallas, N.A."),
    OracleRow("507688", "0597-0020", "2/17/1982", "2/1/1982",
              "Mortgage", "Western Gas Processors, Ltd.", "Republic Bank Dallas N.A. Trustee"),
    OracleRow("1007085", "2929-0210", "2/23/2015", "11/18/2014",
              "Assignment of Oil and Gas Leases",
              "Judy Lea Wickam, formerly Judy L. Jones", "Wickam Minerals LLC"),
    OracleRow("1028924", "3061-0618", "12/30/2016", "12/13/2016",
              "Affidavit of Survivorship", "Charles M. Christensen", "The Public"),
    OracleRow("1028925", "3061-0624", "12/30/2016", "12/13/2016",
              "Quit Claim Deed", "Charles M. Christensen et al", "J&R Christensen Land, LLC"),
    OracleRow("1014885", "2973-0005", "9/14/2015", "9/1/2015",
              "Assignment, Bill of Sale and Conveyance",
              "Anadarko E&P Onshore LLC", "Moriah Powder River, LLC"),
    OracleRow("1014891", "2974-0022", "9/14/2015", "9/1/2015",
              "Bill of Sale", "WPX Energy Rocky Mountain, LLC", "Moriah Powder River, LLC"),
    OracleRow("523059", "0655-0394", "1/4/1983", "1/3/1983",
              "Warranty Deed", "Charles M. Christensen et ux", "Janet Kay Christensen"),
]


def test_digit_distance():
    assert digit_distance("500171", "500112") == 2
    assert digit_distance("521831", "522831") == 1
    assert digit_distance("1007025", "1007085") == 1
    assert digit_distance("12345", "123456") == -1     # length mismatch
    assert digit_distance("500112", "500112") == 0


@pytest.mark.parametrize(
    "ledger,truth,ev_hint",
    [
        # The three-in-a-row Unit Agreement failure, corroborated by rec date + parties.
        ("500171", "500112", "recorded date"),
        ("500172", "500113", "recorded date"),
        ("501189", "500114", "recorded date"),
        # The two Christensen warranty deeds, corroborated by book/page.
        ("521831", "522831", "book/page"),
        ("521832", "522832", "book/page"),
        # The 1007025 phantom omission.
        ("1007025", "1007085", "book/page"),
        # Affidavit / quitclaim pair.
        ("1028821", "1028924", "book/page"),
        ("1028825", "1028925", "book/page"),
    ],
)
def test_face_proved_misreads_are_corrected(ledger, truth, ev_hint):
    """Each real misread must be proposed, with the truth ranked first."""
    o = next(r for r in ORACLE if r.docno == truth)
    s = Suspect(docno=ledger, bookpage=o.bookpage, rec_date=o.rec_date,
                grantor=o.grantor, grantee=o.grantee)
    res = suggest(s, ORACLE, max_digit_distance=3)
    assert res["status"] == "CORRECTION_PROPOSED"
    assert res["candidates"][0]["docno"] == truth
    assert any(ev_hint in e for e in res["candidates"][0]["evidence"])


def test_correct_docno_is_confirmed_not_corrected():
    o = next(r for r in ORACLE if r.docno == "523059")
    s = Suspect(docno="523059", bookpage=o.bookpage, rec_date=o.rec_date)
    assert suggest(s, ORACLE)["status"] == "CONFIRMED"


def test_corroboration_is_mandatory():
    """A numerically-near neighbour with NO supporting evidence is never proposed."""
    s = Suspect(docno="500111")           # one digit from 500112, but no evidence at all
    res = suggest(s, ORACLE)
    assert res["status"] == "NO_ORACLE_MATCH"
    assert res["candidates"] == []


def test_distant_number_is_not_corrected():
    """Proximity bound holds: a far number is not dragged onto an oracle row."""
    o = next(r for r in ORACLE if r.docno == "500112")
    s = Suspect(docno="999999", bookpage=o.bookpage, rec_date=o.rec_date)
    assert suggest(s, ORACLE)["status"] == "NO_ORACLE_MATCH"


def test_ambiguous_when_both_readings_exist():
    """522831 is real AND 522832 is one digit away with shared date -> adjudicate on the face."""
    o = next(r for r in ORACLE if r.docno == "522831")
    s = Suspect(docno="522831", rec_date=o.rec_date, doc_date=o.doc_date)
    res = suggest(s, ORACLE, max_digit_distance=1)
    assert res["status"] == "AMBIGUOUS"


def test_unparseable_suspect_fails_closed():
    assert suggest(Suspect(docno="not-a-number"), ORACLE)["status"] == "UNPARSEABLE"


def test_audit_reproduces_the_measured_page_error_rate():
    """Eight known-bad ledger numbers -> eight corrections proposed, 100% of that set."""
    bad = ["500171", "500172", "501189", "521831", "521832",
           "1007025", "1028821", "1028825"]
    truth = {"500171": "500112", "500172": "500113", "501189": "500114",
             "521831": "522831", "521832": "522832", "1007025": "1007085",
             "1028821": "1028924", "1028825": "1028925"}
    suspects = []
    for b in bad:
        o = next(r for r in ORACLE if r.docno == truth[b])
        suspects.append(Suspect(docno=b, bookpage=o.bookpage, rec_date=o.rec_date,
                                grantor=o.grantor, grantee=o.grantee))
    rep = audit(suspects, ORACLE, max_digit_distance=3)
    assert rep["checked"] == 8
    assert rep["corrections_proposed"] == 8
    assert rep["error_rate"] == 1.0
    assert rep["counts"]["CORRECTION_PROPOSED"] == 8


def test_audit_on_clean_rows_proposes_nothing():
    o = next(r for r in ORACLE if r.docno == "523059")
    rep = audit([Suspect(docno="523059", bookpage=o.bookpage, rec_date=o.rec_date)], ORACLE)
    assert rep["corrections_proposed"] == 0
    assert rep["error_rate"] == 0.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
