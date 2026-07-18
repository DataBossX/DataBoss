"""Tests for legal_desc, review roles, and health/status reporting."""

from fractions import Fraction
from pathlib import Path

from core.land_title_os.evidence import Conclusion, EvidenceEntry, EvidenceLedger
from core.land_title_os.health import assess, status_report
from core.land_title_os.legal_desc import parse, reconcile_acreage
from core.land_title_os.manifest import ProjectManifest
from core.land_title_os.review import (
    deliverable_review, evidence_review, math_review, render, run_reviews,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
BECKHAM = REPO_ROOT / "projects" / "OK-BECKHAM-32-11N-25W"


# -- legal descriptions ------------------------------------------------------

def test_aliquot_acreage_matches_beckham_assessor_rows():
    # the register's surface table, which totals exactly 640.00
    cases = {
        "S/2 N/2 SW/4": 40, "SE/4 NE/4": 40, "SW/4 NW/4": 40,
        "N/2 NW/4": 80, "SE/4 NW/4": 40, "NE/4": 160,
    }
    for text, acres in cases.items():
        d = parse(text)
        assert d.gross_acres == Fraction(acres), text


def test_multi_tract_and_exception():
    d = parse("S/2 SW/4 and W/2 SE/4")
    assert len(d.tracts) == 2 and d.gross_acres == Fraction(160)
    d = parse("E/2 SE/4 less 12.72 acres")
    assert d.gross_acres == Fraction("67.28")
    assert any("exception" in n for n in d.notes)


def test_section_township_range_forms():
    d = parse("NE/4 of Section 32, Township 11 North, Range 25 West")
    assert (d.section, d.township, d.range) == ("32", "11N", "25W")
    d2 = parse("32-11N-25W: N/2 NW/4")
    assert (d2.section, d2.township, d2.range) == ("32", "11N", "25W")
    assert d2.gross_acres == Fraction(80)


def test_lots_and_metes_are_open_not_guessed():
    d = parse("Lots 3 and 4 and S/2 NW/4")
    lots = [t for t in d.tracts if t.lot]
    assert len(lots) == 2 and all(t.acres is None for t in lots)
    assert d.gross_acres is None          # partial totals would mislead
    d2 = parse("a tract by metes and bounds containing 12.72 acres")
    assert d2.gross_acres is None


def test_depth_limitation_captured():
    d = parse("E/2 SE/4 from 11,100 feet to 19,480 feet")
    assert "11,100" in d.depth_limitation
    assert d.gross_acres == Fraction(80)


def test_full_section_and_reconciliation():
    assert parse("All of Section 32-11N-25W").gross_acres == Fraction(640)
    total, problems = reconcile_acreage(
        ["S/2 N/2 SW/4", "SE/4 NE/4", "S/2 SW/4 and W/2 SE/4", "SW/4 NW/4",
         "N/2 N/2 SW/4", "N/2 NW/4", "N/2 NE/4 and SW/4 NE/4",
         "E/2 SE/4 less 12.72 acres", "SE/4 NW/4"],
        Fraction("627.28"))
    assert problems == [] and total == Fraction("627.28")
    _, problems = reconcile_acreage(["NE/4"], 640)
    assert problems and "!=" in problems[0]


# -- review roles ------------------------------------------------------------

def test_evidence_review_flags_weak_and_unverified(tmp_path):
    ledger = EvidenceLedger(tmp_path / "e.jsonl")
    weak = ledger.add_evidence(EvidenceEntry(
        source_document="AST-1", authority_rank=7, extracted_text="ai guess",
        confidence={"extraction": 0.3}))
    ledger.add_conclusion(Conclusion(statement="X owns 1/2", evidence_ids=[weak],
                                     kind="ownership"))
    findings = evidence_review(ledger)
    msgs = " | ".join(f.message for f in findings)
    assert "weak sources" in msgs and "not human-verified" in msgs
    assert "low unverified confidence" in msgs


def test_math_review_combines_qa_and_acreage():
    sheets = {"Title": [{"Owner": "A", "Interest": "1/2"},
                        {"Owner": "B", "Interest": "1/4"}]}
    findings = math_review(sheets, tract_descriptions=["NE/4"],
                           expected_section_acres=640)
    msgs = " | ".join(f.message for f in findings)
    assert "ownership_total" in msgs and "acreage reconciliation" in msgs


def test_deliverable_review_against_manifest(tmp_path):
    m = ProjectManifest(project_id="T", client="C", jurisdiction="OK", county="X",
                        section="1", township="1N", range="1W",
                        templates=[{"sheets": ["Overview", "Title", "Runsheet"]}])
    findings = deliverable_review(["Overview", "Runsheet", "Rogue"], m)
    rules = " | ".join(f.message for f in findings)
    assert "template_missing_sheet" in rules and "template_unexpected_sheet" in rules
    assert deliverable_review(["Overview", "Title", "Runsheet"], m) == []


def test_run_reviews_on_real_beckham_passes_evidence_role():
    # the backfilled ledger is fully human-verified; evidence role must not fire
    findings = run_reviews(BECKHAM)
    assert [f for f in findings if f.role == "evidence"] == []
    assert "ALL REVIEWS PASS" in render([])
    assert "REVIEW FAILURES" in render(
        math_review({"Title": [{"Owner": "A", "Interest": "-1"}]}))


# -- health / status ---------------------------------------------------------

def test_health_and_status_on_real_beckham():
    health = assess(BECKHAM)
    assert health.project_id == "OK-BECKHAM-32-11N-25W"
    assert health.overall == "BLOCKED"          # critical open items exist
    by_name = {d.name: d for d in health.dimensions}
    assert by_name["sources"].state == "OK"
    assert by_name["open_items"].state == "BLOCKED"

    report = status_report(BECKHAM)
    assert "Overall: BLOCKED" in report
    assert "Current blockers" in report and "OKCR" in report
    # counts and items only — never an invented completion percentage
    assert "complete" not in report.lower() or "% complete" not in report.lower()
    assert "Decisions needed" in report


def test_health_clean_project(tmp_path):
    proj = tmp_path / "OK-CLEAN-1"
    ProjectManifest(project_id="OK-CLEAN-1", client="C", jurisdiction="OK",
                    county="X", section="1", township="1N", range="1W",
                    source_locations=[{"store": "local", "id": "/data"}],
                    deliverables=[{"name": "r.xlsx", "status": "APPROVED"}]).save(
        proj / "manifest.json")
    health = assess(proj)
    assert health.overall == "ATTENTION"        # no evidence ledger yet
    assert {d.name: d.state for d in health.dimensions}["open_items"] == "OK"
