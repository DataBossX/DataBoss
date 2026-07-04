"""Tests for the OGL<->runsheet chaining engine and chain-out reconciliation."""

from fractions import Fraction

from horizon.chaining import (
    OGLRecord,
    RunsheetNote,
    build_cross_reference,
    find_chain_breaks,
    normalize_instrument,
    reconcile_chain,
)
from horizon.interest import FULL


def test_normalize_instrument():
    assert normalize_instrument("2019-001234") == "2019001234"
    assert normalize_instrument("#2019 001234") == "2019001234"
    assert normalize_instrument(None) == ""


def test_cross_reference_matches_on_instrument_number():
    ogl = [OGLRecord(instrument_number="2019-001", grantor="A", grantee="B")]
    notes = [RunsheetNote(instrument_number="2019 001", note="leased")]
    xref = build_cross_reference(ogl, notes)
    assert "2019001" in xref
    assert xref["2019001"].matched
    assert xref["2019001"].status == "matched"


def test_cross_reference_detects_breaks():
    ogl = [OGLRecord(instrument_number="100"), OGLRecord(instrument_number="200")]
    notes = [RunsheetNote(instrument_number="100"), RunsheetNote(instrument_number="999")]
    xref = build_cross_reference(ogl, notes)
    breaks = find_chain_breaks(xref)
    statuses = {c.key: c.status for c in breaks}
    assert statuses["200"] == "unreferenced_ogl"  # OGL never noted
    assert statuses["999"] == "orphan_note"        # note with no OGL
    assert "100" not in statuses                    # matched, not a break


def test_reconcile_chain_balances_full_estate():
    records = [
        OGLRecord(instrument_number="1", grantor="Root", grantee="X", conveyed_interest="1/2"),
        OGLRecord(instrument_number="2", grantor="X", grantee="Y", conveyed_interest="1/4"),
    ]
    result = reconcile_chain("Tract A", records, starting_interest=FULL)
    assert not result.needs_examiner_review
    # First link: grantor held 8/8, retained 1/2; grantee X now holds 1/2.
    assert result.links[0].reconciliation.retained == Fraction(1, 2)
    assert result.links[0].holder_after == Fraction(1, 2)
    # Second link: X held 1/2, conveyed 1/4, retained 1/4.
    assert result.links[1].reconciliation.retained == Fraction(1, 4)


def test_reconcile_chain_unknown_start_flags_review():
    records = [OGLRecord(instrument_number="1", grantor="?", grantee="X", conveyed_interest="1/2")]
    result = reconcile_chain("Tract B", records, starting_interest=None)
    assert result.needs_examiner_review
    assert any("undetermined" in r.lower() for r in result.review_reasons)


def test_reconcile_chain_over_conveyance_flags_review():
    records = [
        OGLRecord(instrument_number="1", grantor="Root", grantee="X", conveyed_interest="1/2"),
        # X only holds 1/2 but purports to convey 3/4 -> over-conveyance.
        OGLRecord(instrument_number="2", grantor="X", grantee="Y", conveyed_interest="3/4"),
    ]
    result = reconcile_chain("Tract C", records, starting_interest=FULL)
    assert result.needs_examiner_review
    assert result.links[1].reconciliation.status == "over_conveyance"


def test_reconcile_chain_legal_mismatch_flags_review():
    records = [
        OGLRecord(instrument_number="1", grantor="Root", grantee="X",
                  conveyed_interest="1/2", legal_description="NE/4 Section 99"),
    ]
    result = reconcile_chain("Tract D", records, starting_interest=FULL,
                             tract_legal="SW/4 Section 31")
    assert result.needs_examiner_review
    assert not result.links[0].tied_to_legal
