import json
import sqlite3
from pathlib import Path

import pytest

from databossx.control_plane import ControlPlane, PromotionError


@pytest.fixture()
def control(tmp_path: Path) -> ControlPlane:
    instance = ControlPlane(tmp_path / "control.sqlite3")
    instance.initialize()
    instance.create_project(
        {
            "project_id": "OK-BECKHAM-32-11N-25W",
            "client": "Horizon",
            "jurisdiction": "Oklahoma",
            "county": "Beckham",
            "section": "32",
            "township": "11N",
            "range": "25W",
        }
    )
    return instance


def test_ingest_is_content_addressed_and_preserves_locations(control, tmp_path):
    first = tmp_path / "instrument.pdf"
    second = tmp_path / "copy.pdf"
    first.write_bytes(b"recorded instrument")
    second.write_bytes(first.read_bytes())

    first_id = control.ingest_asset(
        "OK-BECKHAM-32-11N-25W", first, source_authority=1
    )
    second_id = control.ingest_asset(
        "OK-BECKHAM-32-11N-25W", second, source_authority=2
    )

    assert first_id == second_id
    assert first.read_bytes() == b"recorded instrument"
    with control.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM asset_locations").fetchone()[0] == 2


def test_manifest_and_evidence_are_immutable(control, tmp_path):
    source = tmp_path / "deed.txt"
    source.write_text("Book 12 Page 34", encoding="utf-8")
    asset_id = control.ingest_asset(
        "OK-BECKHAM-32-11N-25W", source, source_authority=1
    )
    revision_id = control.create_manifest_revision(
        "OK-BECKHAM-32-11N-25W",
        {"required_checks": ["evidence", "math", "format"]},
        [asset_id],
    )
    evidence_id = control.record_evidence(
        project_id="OK-BECKHAM-32-11N-25W",
        asset_id=asset_id,
        locator="page 1",
        citation="Book 12/Page 34",
        extracted_text="conveys an undivided 1/2 mineral interest",
        conclusion="Grantor conveyed 1/2 mineral interest",
        confidence={"extraction": 0.98, "legal_description": 0.9},
    )

    with control.connect() as connection:
        payload = connection.execute(
            "SELECT payload_json FROM manifest_revisions WHERE id = ?", (revision_id,)
        ).fetchone()[0]
        assert json.loads(payload)["asset_ids"] == [asset_id]
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE evidence SET conclusion = 'changed' WHERE id = ?", (evidence_id,)
            )


def test_promotion_is_sequential_qa_gated_and_human_gated(control, tmp_path):
    output = tmp_path / "report.xlsx"
    output.write_bytes(b"workbook")
    project_id = "OK-BECKHAM-32-11N-25W"
    asset_id = control.ingest_asset(project_id, output, source_authority=5, role="deliverable")
    manifest_id = control.create_manifest_revision(project_id, {}, [asset_id])
    evidence_id = control.record_evidence(
        project_id=project_id,
        asset_id=asset_id,
        locator="Title!B12",
        extracted_text="20.00 NMA",
        conclusion="Owner has 20 NMA",
        confidence={"extraction": 1.0, "calculation": 1.0},
    )
    run_id = control.start_run(
        project_id=project_id,
        manifest_revision_id=manifest_id,
        agent="calculation-agent",
        model="deterministic",
        prompt_version="ownership-v1",
    )
    control.finish_run(run_id, status="SUCCEEDED", output_asset_ids=[asset_id])

    with pytest.raises(PromotionError, match="invalid transition"):
        control.promote(
            project_id=project_id,
            asset_id=asset_id,
            to_state="APPROVED",
            actor="agent",
            reason="skip controls",
        )

    for state in ("STAGING", "EXTRACTED", "RECONCILED"):
        control.promote(
            project_id=project_id,
            asset_id=asset_id,
            to_state=state,
            actor="pipeline",
            reason=f"completed {state.lower()} controls",
        )

    control.record_qa(
        project_id=project_id,
        run_id=run_id,
        subject_id=asset_id,
        check_name="ownership_totals",
        severity="error",
        passed=False,
        detail="totals do not reconcile",
        evidence_ids=[evidence_id],
    )
    with pytest.raises(PromotionError, match="blocking QA"):
        control.promote(
            project_id=project_id,
            asset_id=asset_id,
            to_state="QA",
            actor="qa-agent",
            reason="QA attempted",
        )

    control.record_qa(
        project_id=project_id,
        run_id=run_id,
        subject_id=asset_id,
        check_name="ownership_totals",
        severity="error",
        passed=True,
        detail="corrected totals reconcile",
        evidence_ids=[evidence_id],
    )
    control.promote(
        project_id=project_id,
        asset_id=asset_id,
        to_state="QA",
        actor="qa-agent",
        reason="all deterministic checks pass",
    )
    with pytest.raises(PromotionError, match="human approval"):
        control.promote(
            project_id=project_id,
            asset_id=asset_id,
            to_state="APPROVED",
            actor="qa-agent",
            reason="agent approval prohibited",
        )
    control.promote(
        project_id=project_id,
        asset_id=asset_id,
        to_state="APPROVED",
        actor="examiner@example.com",
        reason="examiner reviewed evidence, math, and format",
        human_approved=True,
    )

    with control.connect() as connection:
        receipts = connection.execute(
            "SELECT previous_hash, receipt_hash FROM promotions ORDER BY created_at, id"
        ).fetchall()
    assert len(receipts) == 5
    assert receipts[0]["previous_hash"] is None
    assert all(receipts[index]["previous_hash"] for index in range(1, len(receipts)))


def test_initialize_creates_verified_backup(tmp_path):
    database = tmp_path / "control.sqlite3"
    control = ControlPlane(database)
    assert control.initialize() is None
    backup = control.initialize()
    assert backup is not None
    assert backup.exists()
    assert backup.read_bytes() == database.read_bytes()
