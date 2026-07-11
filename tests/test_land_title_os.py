"""Tests for the core/land_title_os control layer."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from core.land_title_os.assets import AssetInventory
from core.land_title_os.evidence import Conclusion, EvidenceEntry, EvidenceLedger
from core.land_title_os.issues import IssueRegister, OpenItem
from core.land_title_os.manifest import ProjectManifest, find_manifests
from core.land_title_os.promotion import PromotionEngine, PromotionError
from core.land_title_os.qa_engine import (
    Finding, check_chronology, check_template_sheets, parse_interest,
    run_standard_checks,
)
from core.land_title_os.receipts import ReceiptLedger, RunReceipt
from core.land_title_os.util import sha256_file, stable_id

REPO_ROOT = Path(__file__).resolve().parent.parent


# -- manifest ---------------------------------------------------------------

def test_manifest_roundtrip(tmp_path):
    m = ProjectManifest(project_id="OK-TEST-1", client="Acme", jurisdiction="Oklahoma",
                        county="Beckham", section="32", township="11N", range="25W")
    p = tmp_path / "manifest.json"
    m.save(p)
    loaded = ProjectManifest.load(p)
    assert loaded.project_id == "OK-TEST-1"
    assert loaded.range == "25W"


def test_manifest_rejects_missing_fields(tmp_path):
    m = ProjectManifest(project_id="", client="Acme", jurisdiction="OK",
                        county="X", section="1", township="1N", range="1W")
    with pytest.raises(ValueError):
        m.save(tmp_path / "bad.json")


def test_beckham_manifest_is_valid():
    path = REPO_ROOT / "projects" / "OK-BECKHAM-32-11N-25W" / "manifest.json"
    m = ProjectManifest.load(path)
    assert m.client == "Diversified"
    assert m.county == "Beckham"
    assert any("OKCR" in i["description"] for i in m.open_issues)
    assert find_manifests(REPO_ROOT / "projects")


# -- assets -------------------------------------------------------------------

def test_asset_inventory_idempotent_and_duplicates(tmp_path):
    (tmp_path / "docs").mkdir()
    a = tmp_path / "docs" / "deed1.txt"
    b = tmp_path / "docs" / "deed1_copy.txt"
    c = tmp_path / "docs" / "lease.txt"
    a.write_text("warranty deed content")
    b.write_text("warranty deed content")   # byte-identical duplicate
    c.write_text("oil and gas lease")

    inv = AssetInventory(tmp_path / "assets.db")
    assets = inv.scan_directory(tmp_path / "docs", project_id="OK-TEST-1")
    assert len(assets) == 3
    # rescanning mints no new identities
    inv.scan_directory(tmp_path / "docs", project_id="OK-TEST-1")
    assert inv.count() == 3

    groups = inv.duplicate_groups()
    assert len(groups) == 1
    (paths,) = groups.values()
    assert {Path(p).name for p in paths} == {"deed1.txt", "deed1_copy.txt"}
    assert inv.by_project("OK-TEST-1")
    inv.close()


def test_asset_remote_registration(tmp_path):
    inv = AssetInventory(tmp_path / "assets.db")
    asset = inv.register_remote("1gk0hofK94kjkw8ygHFtE-3YmtC-hyw4H", store="gdrive",
                                project_id="OK-BECKHAM-32-11N-25W",
                                security_class="client-confidential")
    assert asset.asset_id.startswith("AST-")
    assert inv.get(asset.asset_id)["store"] == "gdrive"
    inv.close()


# -- evidence -----------------------------------------------------------------

def test_conclusion_requires_evidence(tmp_path):
    ledger = EvidenceLedger(tmp_path / "evidence.jsonl")
    with pytest.raises(ValueError):
        ledger.add_conclusion(Conclusion(statement="X owns 1/2"))
    with pytest.raises(ValueError):
        ledger.add_conclusion(Conclusion(statement="X owns 1/2",
                                         evidence_ids=["EVD-doesnotexist"]))


def test_evidence_authority_and_provenance(tmp_path):
    ledger = EvidenceLedger(tmp_path / "evidence.jsonl")
    weak = ledger.add_evidence(EvidenceEntry(
        source_document="AST-1", authority_rank=7, extracted_text="ai read",
        confidence={"extraction": 0.6}))
    strong = ledger.add_evidence(EvidenceEntry(
        source_document="AST-2", authority_rank=1, book_page="1014/75",
        image_reference="Img 4893", extracted_text="recorded deed"))
    cid = ledger.add_conclusion(Conclusion(
        statement="Cutoff instrument is Bk 1014/P75", evidence_ids=[weak, strong]))
    assert ledger.best_authority(cid) == 1
    prov = ledger.provenance(cid)
    assert len(prov["evidence"]) == 2
    assert ledger.unverified_conclusions()

    # persistence round-trip
    reloaded = EvidenceLedger(tmp_path / "evidence.jsonl")
    assert cid in reloaded.conclusions
    assert reloaded.best_authority(cid) == 1


def test_evidence_rejects_bad_axes(tmp_path):
    with pytest.raises(ValueError):
        EvidenceEntry(source_document="AST-1", authority_rank=1,
                      confidence={"vibes": 0.9})
    with pytest.raises(ValueError):
        EvidenceEntry(source_document="AST-1", authority_rank=99)


# -- receipts ------------------------------------------------------------------

def test_receipt_chain_detects_tampering(tmp_path):
    ledger = ReceiptLedger(tmp_path / "receipts.jsonl")
    ledger.record(RunReceipt(agent="extractor", action="extract"))
    ledger.record(RunReceipt(agent="qa", action="validate", tests={"passed": 5}))
    assert ledger.verify_chain() == []

    # tamper with the first receipt
    lines = (tmp_path / "receipts.jsonl").read_text().splitlines()
    rec = json.loads(lines[0])
    rec["agent"] = "impostor"
    lines[0] = json.dumps(rec)
    (tmp_path / "receipts.jsonl").write_text("\n".join(lines) + "\n")
    problems = ReceiptLedger(tmp_path / "receipts.jsonl").verify_chain()
    assert problems and "altered" in problems[0]


# -- promotion -------------------------------------------------------------------

def _engine(tmp_path):
    receipts = ReceiptLedger(tmp_path / "receipts.jsonl")
    return PromotionEngine(tmp_path / "promotion_state.json", receipts), receipts


def test_promotion_happy_path_and_gates(tmp_path):
    engine, receipts = _engine(tmp_path)
    f = tmp_path / "report.xlsx"
    f.write_text("workbook bytes")

    engine.register_check("STAGING", "file_nonempty", lambda p: p.stat().st_size > 0)
    rec = engine.promote(f, "STAGING", actor="intake-agent")
    assert rec.checks_passed == ["file_nonempty"]
    assert engine.stage_of(f) == "STAGING"

    # stage skipping is illegal
    with pytest.raises(PromotionError):
        engine.promote(f, "QA", actor="intake-agent")

    engine.promote(f, "EXTRACTED", actor="extract-agent")
    engine.promote(f, "RECONCILED", actor="reconcile-agent")
    engine.promote(f, "QA", actor="qa-agent")

    # human gate: APPROVED requires human_approved=True
    with pytest.raises(PromotionError):
        engine.promote(f, "APPROVED", actor="qa-agent")
    engine.promote(f, "APPROVED", actor="Rodney", human_approved=True)
    engine.promote(f, "DELIVERED", actor="Rodney", human_approved=True)
    assert engine.stage_of(f) == "DELIVERED"
    assert receipts.verify_chain() == []
    assert len(receipts.all()) == 6


def test_promotion_failing_check_blocks(tmp_path):
    engine, _ = _engine(tmp_path)
    f = tmp_path / "empty.xlsx"
    f.write_text("")
    engine.register_check("STAGING", "file_nonempty", lambda p: p.stat().st_size > 0)
    with pytest.raises(PromotionError):
        engine.promote(f, "STAGING", actor="intake-agent")
    assert engine.stage_of(f) == "SOURCE"


# -- issues -----------------------------------------------------------------------

def test_issue_lifecycle(tmp_path):
    reg = IssueRegister(tmp_path / "issues.json")
    iid = reg.open_item(OpenItem(
        description="Resolve I-2011-001515 vs I-2011-001565", severity="high",
        affected_tract="Tract 3", required_research="OKCR reception lookup"))
    assert reg.open_items(severity="high")
    with pytest.raises(ValueError):
        reg.resolve(iid, "")
    item = reg.resolve(iid, "OKCR confirms 1565", approved_by="Rodney")
    assert item.status == "approved"
    assert not reg.open_items()
    # persistence
    assert IssueRegister(tmp_path / "issues.json").items[iid].resolution


def test_issue_rejects_bad_severity():
    with pytest.raises(ValueError):
        OpenItem(description="x", severity="catastrophic")


# -- qa engine ----------------------------------------------------------------------

def test_parse_interest_forms():
    assert parse_interest("1/2") == Fraction(1, 2)
    assert parse_interest("UND 20/260") == Fraction(1, 13)
    assert parse_interest("0.125") == Fraction(1, 8)
    assert parse_interest(1) == Fraction(1)
    assert parse_interest("") is None
    assert parse_interest("n/a") is None


def test_standard_checks_catch_title_defects():
    sheets = {
        "Title": [
            {"Owner": "Alice Kirk", "Interest": "1/2"},
            {"Owner": "Bob Kirk", "Interest": "-1/4"},        # negative
            {"Owner": "alice kirk", "Interest": "1/2"},       # duplicate owner
            {"Owner": "", "Interest": "1/2"},                 # unsupported name; breaks total
        ],
        "Runsheet": [
            {"Instrument_Number": "I-1", "Recorded_Date": "1988-04-26"},
            {"Instrument_Number": "", "Recorded_Date": "2026-07-07"},   # missing instrument
            {"Instrument_Number": "I-3", "Recorded_Date": "2011-02-11"},  # out of order
        ],
    }
    findings = run_standard_checks(sheets)
    rules = {f.rule for f in findings}
    assert {"negative_interest", "ownership_total", "duplicate_owner",
            "unsupported_owner_name", "missing_instrument",
            "chronological_chain_break"} <= rules
    # critical findings sort first
    assert findings[0].severity == "critical"
    # every finding carries a recommendation
    assert all(f.recommendation for f in findings)


def test_clean_workbook_passes():
    sheets = {
        "Title": [
            {"Owner": "Alice Kirk", "Interest": "1/2"},
            {"Owner": "Bob Kirk", "Interest": "1/2"},
        ],
        "Runsheet": [
            {"Instrument_Number": "I-1", "Recorded_Date": "1988-04-26"},
            {"Instrument_Number": "I-2", "Recorded_Date": "2026-07-07"},
        ],
    }
    assert run_standard_checks(sheets) == []


def test_template_sheet_check():
    expected = ["Overview", "Title", "Runsheet"]
    findings = check_template_sheets(["Overview", "Runsheet", "Title", "Scratch"], expected)
    rules = {f.rule for f in findings}
    assert "template_unexpected_sheet" in rules
    assert "template_sheet_order" in rules
    assert check_template_sheets(expected, expected) == []


# -- util ---------------------------------------------------------------------------

def test_stable_id_deterministic(tmp_path):
    assert stable_id("AST", "a", "b") == stable_id("AST", "a", "b")
    assert stable_id("AST", "a", "b") != stable_id("AST", "a", "c")
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello")
    assert sha256_file(f) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
