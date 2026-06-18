"""Tests for the rule-based mineral-ownership status logic."""

import status_logic as sl


def _doc(**kw):
    base = {
        "recording_date": "2020-01-01",
        "legal_short": "Sec 1 T7N R63W",
        "instrument": "Warranty Deed",
        "grantor": "",
        "grantee": [],
    }
    base.update(kw)
    return base


def test_no_owner_returns_manual():
    out = sl.decide_status_rule_based("", [_doc()])
    assert out["status"].startswith("Unknown")
    assert out["confidence"] == 0.0


def test_no_docs_returns_manual():
    out = sl.decide_status_rule_based("ACME", [])
    assert out["status"].startswith("Unknown")


def test_no_target_hits():
    out = sl.decide_status_rule_based("ACME", [_doc(legal_short="Sec 9 T7N R63W")])
    assert out["status"].startswith("Unknown")
    assert "No Sec 1" in out["explanation"]


def test_owner_as_grantee_is_current_owner():
    out = sl.decide_status_rule_based("ACME", [_doc(grantee=["ACME"])])
    assert out["status"] == "Current owner of record"
    assert out["confidence"] == 0.85


def test_owner_as_grantor_assigned_out():
    out = sl.decide_status_rule_based("ACME", [_doc(grantor="ACME")])
    assert out["status"] == "Assigned out"


def test_lease_with_owner_as_lessor_is_hbp():
    out = sl.decide_status_rule_based("ACME", [_doc(instrument="Oil & Gas Lease", grantor="ACME")])
    assert out["status"] == "Leased HBP"


def test_latest_doc_wins():
    docs = [
        _doc(recording_date="2019-01-01", grantee=["ACME"]),
        _doc(recording_date="2021-01-01", grantor="ACME"),  # later: assigned out
    ]
    out = sl.decide_status_rule_based("ACME", docs)
    assert out["status"] == "Assigned out"


def test_hits_target_normalizes_punctuation():
    assert sl._hits_target("SEC. 1, T7N R63W") is True
    assert sl._hits_target("") is False
