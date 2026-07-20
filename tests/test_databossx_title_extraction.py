"""Tests for raw-document conveyance extraction and the document-chain fallback."""

from pathlib import Path

import pytest

from databossx.title_extraction import extract_conveyance, extract_conveyances

_DEED1 = """MINERAL DEED
Grantor: UNITED STATES OF AMERICA
Grantee: ALICE SMITH
Instrument No: 2018-0001   Recorded: Book 100 Page 1
Conveys an undivided 1/2 mineral interest in and under:
Section 31, Township 12 North, Range 24 West, containing 160 acres.
"""

_DEED2 = """WARRANTY DEED
Grantor: ALICE SMITH
Grantee: BOB JONES
Instrument No: 2019-0002
Conveys an undivided 1/4 interest in Sec 31 T12N R24W.
"""


def test_extract_conveyance_fields():
    f = extract_conveyance(_DEED1, source="deed1")
    assert f.doc_type == "Mineral Deed"
    assert f.grantor == "UNITED STATES OF AMERICA"
    assert f.grantee == "ALICE SMITH"
    assert f.instrument_number == "2018-0001"
    assert f.conveyed_interest == "1/2"
    assert f.gross_acres == "160"
    # Legal normalized to a canonical S/T/R key.
    assert f.legal_description == "31-12N-24W"
    assert not f.review_flags


def test_legal_normalizes_across_documents():
    # Spelled-out vs abbreviated legals collapse to the same tract key.
    f1 = extract_conveyance(_DEED1)
    f2 = extract_conveyance(_DEED2)
    assert f1.legal_description == f2.legal_description == "31-12N-24W"


def test_review_flags_when_fields_missing():
    f = extract_conveyance("Grantor: A\nGrantee: B\n(nothing else)")
    assert "conveyed interest not found" in f.review_flags
    assert "legal description not found" in f.review_flags


def test_extract_conveyances_orders_and_filters():
    ogl = extract_conveyances({"d2": _DEED2, "d1": _DEED1,
                               "junk": "no parties or instrument here"})
    assert [r.instrument_number for r in ogl] == ["2018-0001", "2019-0002"]
    assert all(r.legal_description == "31-12N-24W" for r in ogl)


def test_document_only_chain_reconciles_exactly():
    from horizon.pipeline import chain_to_report

    from databossx.title_extraction import conveyance_notes
    ogl = extract_conveyances({"d1": _DEED1, "d2": _DEED2})
    build = chain_to_report(ogl, conveyance_notes(ogl), section="31-12N-24W")
    rows = {r.instrument_number: r for r in build.report.rows}
    # A clean US -> Alice -> Bob chain ties out with exact fractions, no review.
    assert rows["2018-0001"].status == "ok"
    assert rows["2019-0002"].status == "ok"
    assert rows["2018-0001"].retained_interest == "1/2"
    assert rows["2019-0002"].conveyed_interest == "1/4"


def test_end_to_end_document_only_project(tmp_path):
    """A project folder of loose deeds (no OGL workbook) still yields a chain."""
    from databossx.command_center import run_project

    src = tmp_path / "DeedsOnly"
    src.mkdir()
    (src / "deed_2018.txt").write_text(_DEED1, encoding="utf-8")
    (src / "deed_2019.txt").write_text(_DEED2, encoding="utf-8")

    result = run_project("golden_demo", root=str(src),
                         output_dir=str(tmp_path / "out"), make_pdf=False)
    assert result.ok
    # The chain came from the documents, not a workbook.
    assert result.counts["runsheet_rows"] == 2
    assert any("extracted from documents" in w for w in result.warnings)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
