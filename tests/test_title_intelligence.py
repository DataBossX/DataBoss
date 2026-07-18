"""Tests for the DataBossX title-intelligence connective layer.

These exercise the full landman path: document -> conveyance fact extraction
(grocery pipeline) -> exact interest chaining + validation (horizon) -> persisted
derived artifact (databossx foundation).
"""

from __future__ import annotations

from pathlib import Path

from databossx.config import DataBossConfig
from databossx.database import DataBossDatabase
from databossx.title_intelligence import (
    SAMPLE_DEEDS,
    build_title_analysis,
    extract_conveyance,
    seed_demo_project,
)

# Map SAMPLE_DEEDS by filename for readable, order-independent access.
_DEEDS = dict(SAMPLE_DEEDS)


def _conveyances(filenames):
    return [extract_conveyance(fn, _DEEDS[fn]) for fn in filenames]


def test_extract_conveyance_reads_grantor_grantee_interest_and_legal():
    fact = extract_conveyance(
        "01_mineral_deed_anderson_baker.txt", _DEEDS["01_mineral_deed_anderson_baker.txt"]
    )
    assert fact.grantor == "Alice Anderson"
    assert fact.grantee == "Bob Baker"
    assert fact.conveyed_interest == "1/2"
    assert "Section 31" in fact.legal_description
    assert fact.gross_acres == "640"
    assert fact.instrument_number == "20180001"
    assert fact.doc_type == "Mineral Deed"
    assert "deed" in fact.categories
    assert fact.is_conveyance is True


def test_lease_is_supporting_not_a_conveyance():
    fact = extract_conveyance(
        "05_oil_and_gas_lease_evans_operator.txt",
        _DEEDS["05_oil_and_gas_lease_evans_operator.txt"],
    )
    assert fact.is_conveyance is False
    assert "oil and gas lease" in fact.categories


def test_clean_chain_ties_out_with_exact_interest_and_net_acres():
    conveyances = _conveyances([
        "01_mineral_deed_anderson_baker.txt",
        "02_mineral_deed_baker_chen.txt",
        "03_warranty_deed_chen_diaz.txt",
        "04_mineral_deed_diaz_evans.txt",
    ])
    analysis = build_title_analysis(conveyances, section="Section 31, T12N, R24W")

    assert analysis["summary"]["conveyance_documents"] == 4
    assert analysis["summary"]["tracts"] == 1
    assert analysis["summary"]["over_conveyances"] == 0
    assert analysis["summary"]["overall_status"] == "CLEAR"

    owner = analysis["ownership"][0]
    assert owner["ties_out"] is True
    assert owner["current_owner"] == "Erin Evans"
    assert owner["current_interest"] == "1/8"
    # 1/8 of 640 gross acres, computed with exact fraction math.
    assert owner["net_mineral_acres"] == "80.0000"


def test_over_conveyance_is_flagged_not_fabricated():
    conveyances = _conveyances([
        "06_mineral_deed_frank_isaac.txt",
        "07_mineral_deed_isaac_jack_overconveyance.txt",
    ])
    analysis = build_title_analysis(conveyances, section="Section 32, T12N, R24W")

    assert analysis["summary"]["over_conveyances"] >= 1
    assert analysis["summary"]["overall_status"] == "REVIEW REQUIRED"
    owner = analysis["ownership"][0]
    assert owner["ties_out"] is False
    assert owner["review_reasons"]  # non-empty examiner reasons
    # The over-conveying row carries a precise, non-fabricated remark.
    over_rows = [r for r in analysis["chain_rows"] if "over-conveyance" in (r["remarks"] or "").lower()]
    assert over_rows


def test_grantor_continuity_break_is_detected():
    # Anderson->Baker, then a deed whose grantor is NOT Baker (chain-of-title gap).
    conveyances = _conveyances([
        "01_mineral_deed_anderson_baker.txt",
        "03_warranty_deed_chen_diaz.txt",  # grantor Carol Chen != prior grantee Bob Baker
    ])
    analysis = build_title_analysis(conveyances, section="Section 31, T12N, R24W")
    assert analysis["summary"]["rows_need_review"] >= 1
    remarks = " ".join((r["remarks"] or "") for r in analysis["chain_rows"]).lower()
    assert "chain-of-title break" in remarks


def test_seed_demo_project_persists_auditable_artifact(tmp_path):
    config = DataBossConfig.from_repo_root(tmp_path / "repo")
    result = seed_demo_project(config)
    project_id = result["project_id"]
    analysis = result["analysis"]

    # 6 ownership-conveying deeds (4 on Sec 31, 2 on Sec 32) + 1 supporting lease.
    assert analysis["summary"]["documents"] == 7
    assert analysis["summary"]["conveyance_documents"] == 6
    assert analysis["summary"]["supporting_documents"] == 1
    assert analysis["summary"]["tracts"] == 2
    assert analysis["summary"]["over_conveyances"] >= 1
    assert "artifact_id" in analysis
    assert Path(analysis["artifact_path"]).exists()

    db = DataBossDatabase(config.project_db_path(project_id))
    artifacts = db.fetchall(
        "SELECT artifact_type FROM derived_artifacts WHERE project_id = ?", (project_id,)
    )
    assert any(row["artifact_type"] == "title_analysis" for row in artifacts)
    audit = db.fetchone(
        "SELECT COUNT(*) AS n FROM audit_events WHERE project_id = ? AND event_type = 'title.analyzed'",
        (project_id,),
    )
    assert audit["n"] >= 1
    lineage = db.fetchone(
        """
        SELECT COUNT(*) AS n FROM artifact_lineage al
          JOIN derived_artifacts da ON da.id = al.derived_artifact_id
         WHERE da.project_id = ?
        """,
        (project_id,),
    )
    assert lineage["n"] >= 6
