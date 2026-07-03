"""Regression tests for the post-review correctness fixes."""

from __future__ import annotations

import sqlite3
import types
from fractions import Fraction

import pytest

from validation_agent.config.settings import config
from validation_agent.db.db_client import DatabaseManager
from validation_agent.validators._helpers import is_total_row
from validation_agent.validators.val_acreage import AcreageValidator
from validation_agent.validators.val_interest import InterestValidator


def _cell(row, value):
    return types.SimpleNamespace(row=row, value=value, coord=f"A{row}")


def _sheet(name, cells):
    return types.SimpleNamespace(name=name, cells={c.coord: c for c in cells},
                                 header_row=1)


# -- B1: is_total_row must not match party/company names --------------------
def test_is_total_row_exact_match_only():
    party = _sheet("Runsheet", [_cell(2, "Total Petroleum Inc")])
    assert not is_total_row(party, 2)
    summary = _sheet("Runsheet", [_cell(2, "Summary Deed")])
    assert not is_total_row(summary, 2)
    real = _sheet("Tract Summary", [_cell(12, "TOTAL")])
    assert is_total_row(real, 12)


# -- B4: interest normalization vs genuine over-conveyance ------------------
def test_rounded_decimal_is_representational():
    assert InterestValidator._is_rounded_representation("0.333", Fraction(1, 3))
    assert InterestValidator._is_rounded_representation("0.125", Fraction(1, 8))


def test_genuine_mismatch_is_not_representational():
    # 0.5 is not the rounded form of 2/5 (0.4) at one decimal place.
    assert not InterestValidator._is_rounded_representation("0.5", Fraction(2, 5))
    # An exact fraction string is not a decimal -- handled by the residual path.
    assert not InterestValidator._is_rounded_representation("1/3", Fraction(1, 3))


# -- B6: acreage footing prefers a summary tab (no double counting) ---------
def test_acreage_prefers_summary_sheet():
    tracts = [_sheet("Tract 1", []), _sheet("Tract Summary", []),
              _sheet("Tract 2", [])]
    chosen = AcreageValidator._acreage_sheets(tracts)
    assert [s.name for s in chosen] == ["Tract Summary"]


def test_acreage_falls_back_to_all_tracts_without_summary():
    tracts = [_sheet("Tract 1", []), _sheet("Tract 2", [])]
    assert AcreageValidator._acreage_sheets(tracts) == tracts


# -- C3: authorizer denies DROP VIEW / DROP TRIGGER (correct action codes) --
@pytest.fixture()
def dbm(tmp_path):
    m = DatabaseManager(db_path=tmp_path / "t.db", schema_path=config.schema_path)
    m.init()
    return m


def test_authorizer_denies_drop_view(dbm):
    with dbm.connect() as c:
        c.execute("CREATE VIEW v AS SELECT 1")
    with dbm.connect() as c:
        with pytest.raises(sqlite3.DatabaseError):
            c.execute("DROP VIEW v")


# -- C6: sub-cent overage cannot round down under the cap -------------------
def test_spend_guard_blocks_subcent_overage(tmp_path):
    from validation_agent.db.audit_logger import AuditLogger
    from validation_agent.sources.spend_guard import APISpendGuard
    dbm = DatabaseManager(db_path=tmp_path / "s.db", schema_path=config.schema_path)
    dbm.init()
    guard = APISpendGuard(AuditLogger(dbm), cap=100.0)
    guard.commit_spend(99.99997, "prior")
    d = guard.authorize(0.00006)  # true total 100.00003 -> must block
    assert not d.allowed


# -- C1/C2: okcounty parses a bare JSON array and encodes the URL -----------
def test_okcounty_parses_top_level_array():
    from validation_agent.sources.okcounty_client import CurlResponse, OKCountyRecordsClient
    client = OKCountyRecordsClient()
    resp = CurlResponse(ok=True, http_status=200,
                        body=b'[{"id":"42","county":"Roger Mills"}]', error=None)
    rec = client._parse_record(resp, "Roger Mills", "", "", "")
    assert rec is not None and rec.document_id == "42"


def test_okcounty_url_encodes_query(monkeypatch, tmp_path):
    from validation_agent.db.audit_logger import AuditLogger
    from validation_agent.sources.okcounty_client import CurlResponse, OKCountyRecordsClient
    monkeypatch.setenv("OKCOUNTY_USERNAME", "u")
    monkeypatch.setenv("OKCOUNTY_PASSWORD", "p")
    dbm = DatabaseManager(db_path=tmp_path / "o.db", schema_path=config.schema_path)
    dbm.init()
    client = OKCountyRecordsClient(audit=AuditLogger(dbm))
    captured = {}

    def fake_curl(url, **kwargs):
        captured["url"] = url
        return CurlResponse(ok=False, http_status=404, body=b"", error="nf")

    monkeypatch.setattr(client, "_curl", fake_curl)
    client.search_document("Le Flore", book="A&B")
    assert " " not in captured["url"]
    assert "Le+Flore" in captured["url"] or "Le%20Flore" in captured["url"]
    assert "A%26B" in captured["url"]
