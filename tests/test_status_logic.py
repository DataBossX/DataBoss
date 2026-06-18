"""Unit tests for the rule-based status engine (automation/status_logic.py).

This module is pure Python (no heavy deps) so these tests always run.
"""
from automation.status_logic import _hits_target, decide_status_rule_based


def _doc(**kw):
    base = {
        "recording_date": "2024-01-01",
        "legal_short": "SEC 1 T7N R63W",
        "instrument": "WARRANTY DEED",
        "grantor": "",
        "grantee": [],
    }
    base.update(kw)
    return base


def test_hits_target_matches_section_township_range():
    assert _hits_target("Sec 1, T7N, R63W") is True
    assert _hits_target("SECTION 1 T7N R63W") is True


def test_hits_target_rejects_other_sections():
    assert _hits_target("SEC 2 T7N R63W") is False
    assert _hits_target("") is False
    assert _hits_target(None) is False  # type: ignore[arg-type]


def test_no_target_docs_is_manual():
    res = decide_status_rule_based("JANE DOE", [_doc(legal_short="SEC 9 T1N R1W")])
    assert res["status"].startswith("Unknown")


def test_owner_as_grantor_is_assigned_out():
    res = decide_status_rule_based("JANE DOE", [_doc(grantor="JANE DOE")])
    assert res["status"] == "Assigned out"
    assert res["confidence"] == 0.85


def test_owner_lessor_on_lease_is_leased_hbp():
    res = decide_status_rule_based(
        "JANE DOE",
        [_doc(instrument="OIL AND GAS LEASE", grantor="JANE DOE")],
    )
    assert res["status"] == "Leased HBP"


def test_owner_as_grantee_is_current_owner():
    res = decide_status_rule_based(
        "JANE DOE",
        [_doc(grantee=["JANE DOE"], grantor="SOMEONE ELSE")],
    )
    assert res["status"] == "Current owner of record"


def test_latest_doc_wins_by_recording_date():
    docs = [
        _doc(recording_date="2020-01-01", grantee=["JANE DOE"], grantor="X"),
        _doc(recording_date="2023-01-01", grantor="JANE DOE"),
    ]
    res = decide_status_rule_based("JANE DOE", docs)
    assert res["status"] == "Assigned out"
