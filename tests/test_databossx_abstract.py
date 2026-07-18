"""Tests for the chain-of-title abstract / ownership-chain builder."""

import pytest

from databossx.abstract import abstract_narrative, build_abstract


def _rows():
    # Two tracts; tract A has a flagged link.
    return [
        {"instrument_number": "1", "instrument_date": "2018-01-01",
         "doc_type": "Deed", "grantor": "US", "grantee": "Alice",
         "conveyed_interest": "1/2", "retained_interest": "1/2",
         "net_mineral_acres": "80", "legal_description": "Sec 31 T12N R24W",
         "status": "ok", "remarks": ""},
        {"instrument_number": "2", "instrument_date": "2019-02-01",
         "doc_type": "Deed", "grantor": "Alice", "grantee": "Bob",
         "conveyed_interest": "1/4", "retained_interest": "1/4",
         "net_mineral_acres": "40", "legal_description": "Sec 31 T12N R24W",
         "status": "Needs Examiner Review", "remarks": "Chain break: X"},
        {"instrument_number": "9", "instrument_date": "2017-05-01",
         "doc_type": "Patent", "grantor": "State", "grantee": "Carol",
         "conveyed_interest": "1", "retained_interest": "0",
         "net_mineral_acres": "160", "legal_description": "Sec 32 T12N R24W",
         "status": "ok", "remarks": ""},
    ]


def test_groups_by_tract_in_order():
    abstracts = build_abstract(_rows())
    assert len(abstracts) == 2
    a = abstracts[0]
    assert a.legal_description == "Sec 31 T12N R24W"
    assert [e.seq for e in a.entries] == [1, 2]
    assert a.entries[0].grantor == "US" and a.entries[0].grantee == "Alice"


def test_final_grantee_is_apparent_current_holder():
    abstracts = build_abstract(_rows())
    assert abstracts[0].final_grantee == "Bob"
    assert abstracts[1].final_grantee == "Carol"


def test_review_links_are_flagged_not_hidden():
    abstracts = build_abstract(_rows())
    a = abstracts[0]
    assert a.review_count == 1
    assert a.entries[1].needs_review
    # The narrative surfaces the review reason.
    text = a.narrative()
    assert "REVIEW" in text and "Chain break" in text


def test_narrative_is_chronological_plain_language():
    text = abstract_narrative(build_abstract(_rows()))
    assert "US → Alice" in text
    assert "conveys 1/2" in text
    assert "Sec 32 T12N R24W" in text


def test_empty_rows_yield_empty_abstract():
    assert build_abstract([]) == []


def test_works_with_titlerow_objects():
    from horizon.models import TitleRow
    rows = [TitleRow(instrument_number="1", grantor="A", grantee="B",
                     conveyed_interest="1/2", legal_description="Sec 1",
                     status="ok")]
    abstracts = build_abstract(rows)
    assert len(abstracts) == 1
    assert abstracts[0].entries[0].grantee == "B"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
