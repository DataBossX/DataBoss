"""Gate 11 (Source Verification) drives the OKCounty client for real.

Uses an injected fake client so the retrieve/compare logic is exercised without
network or credentials. Covers: match -> PASS, contradiction -> mismatch,
retrieval failure -> unverifiable, and spend-cap block.
"""

from __future__ import annotations

import types

import pytest

pytest.importorskip("openpyxl")

from validation_agent.config.settings import config  # noqa: E402
from validation_agent.core.orchestrator import PerfectionLoopOrchestrator  # noqa: E402
from validation_agent.db.audit_logger import AuditLogger  # noqa: E402
from validation_agent.db.db_client import DatabaseManager  # noqa: E402
from validation_agent.ingestion.manifest_builder import WorkbookManifestBuilder  # noqa: E402
from validation_agent.models import GateStatus  # noqa: E402


class FakeClient:
    def __init__(self, records, *, remaining=100.0, configured=True):
        self._records = records
        self.guard = types.SimpleNamespace(remaining=lambda: remaining)
        self._configured = configured

    def is_configured(self):
        return self._configured

    def search_document(self, county, book="", page="", instrument_number="",
                        run_id=None):
        return self._records.get((book, page, instrument_number))

    @staticmethod
    def verify_against(record, expected_parties, expected_legal):
        return record.verify_result


def _rec(doc_id, verify_result):
    return types.SimpleNamespace(document_id=doc_id, verify_result=verify_result)


def _runsheet(tmp_path):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Runsheet"
    ws.append(["County", "Grantor", "Grantee", "Book", "Page", "Legal Description"])
    ws.append(["Roger Mills", "ALICE", "BOB", 5, 100, "SEC 31-12N-24W"])
    ws.append(["Roger Mills", "BOB", "CAROL", 6, 110, "SEC 31-12N-24W"])
    p = tmp_path / "rs.xlsx"
    wb.save(p)
    return WorkbookManifestBuilder().build("r", 0, p, "sha")


def _orch(tmp_path, fake):
    dbm = DatabaseManager(db_path=tmp_path / "v.db", schema_path=config.schema_path)
    dbm.init()
    return PerfectionLoopOrchestrator(audit=AuditLogger(dbm), source_client=fake)


def _ctx():
    return types.SimpleNamespace(run_id="r")


def test_sources_verified_pass(tmp_path):
    fake = FakeClient({
        ("5", "100", ""): _rec("A", (True, "ok")),
        ("6", "110", ""): _rec("B", (True, "ok")),
    })
    orch = _orch(tmp_path, fake)
    res = orch._gate_source_verification(_ctx(), _runsheet(tmp_path), 0)
    assert res.status is GateStatus.PASS
    assert res.metrics["checked"] == 2


def test_source_contradiction_escalates(tmp_path):
    fake = FakeClient({
        ("5", "100", ""): _rec("A", (True, "ok")),
        ("6", "110", ""): _rec("B", (False, "legal description contradicts workbook")),
    })
    orch = _orch(tmp_path, fake)
    res = orch._gate_source_verification(_ctx(), _runsheet(tmp_path), 0)
    assert res.status is GateStatus.FAIL
    assert any(f.category.value == "source_legal_mismatch" for f in res.findings)


def test_retrieval_failure_is_unverifiable(tmp_path):
    fake = FakeClient({("5", "100", ""): _rec("A", (True, "ok"))})  # 6/110 missing
    orch = _orch(tmp_path, fake)
    res = orch._gate_source_verification(_ctx(), _runsheet(tmp_path), 0)
    assert res.status is GateStatus.FAIL
    assert any(f.category.value == "unverifiable_source" for f in res.findings)


def test_unconfigured_client_skips(tmp_path):
    fake = FakeClient({}, configured=False)
    orch = _orch(tmp_path, fake)
    res = orch._gate_source_verification(_ctx(), _runsheet(tmp_path), 0)
    assert res.status is GateStatus.SKIPPED


def test_spend_cap_blocks_verification(tmp_path):
    fake = FakeClient({("5", "100", ""): _rec("A", (True, "ok"))}, remaining=0.0)
    orch = _orch(tmp_path, fake)
    # Force a positive per-search cost so the pre-check trips (config is frozen).
    old = config.okcounty_cost_per_search
    object.__setattr__(config, "okcounty_cost_per_search", 1.0)
    try:
        res = orch._gate_source_verification(_ctx(), _runsheet(tmp_path), 0)
    finally:
        object.__setattr__(config, "okcounty_cost_per_search", old)
    assert res.status is GateStatus.FAIL
    assert any(f.category.value == "api_spend_blocked" for f in res.findings)
