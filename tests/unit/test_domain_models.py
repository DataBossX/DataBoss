"""Tests for databossx.domain.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from databossx.domain.models import (
    Approval,
    Asset,
    AssetVersion,
    AuditEvent,
    ChainLink,
    Claim,
    ClaimSupport,
    Conflict,
    CurativeItem,
    DerivedArtifact,
    EvidenceSpan,
    Instrument,
    InstrumentParty,
    InterestLedgerEntry,
    Jurisdiction,
    ModelRouteDecision,
    Project,
    RecordingReference,
    ReviewDecision,
    ReviewGate,
    Run,
    SourceConnection,
    SourceSnapshot,
    Task,
    TaskAttempt,
    TaskDependency,
    TaskLease,
    TitleException,
    TitleProject,
    ToolDefinition,
    ToolRun,
    Tract,
    WorkbookCandidate,
    WorkerCapability,
    WorkflowDefinition,
)

NOW = datetime.now(timezone.utc)


def test_project_instantiation_and_mutability():
    project = Project(
        id="p1",
        name="Section 32 Title",
        jurisdiction="Windsor County",
        policy_set="default",
        confidentiality="internal",
        lifecycle_state="DRAFT",
        created_at=NOW,
        updated_at=NOW,
    )
    assert project.name == "Section 32 Title"
    # Project is a mutable entity (frozen=False).
    project.lifecycle_state = "EVIDENCE_LOCKED"
    assert project.lifecycle_state == "EVIDENCE_LOCKED"


def test_asset_version_is_frozen():
    version = AssetVersion(
        id="av1",
        asset_id="a1",
        locator="s3://bucket/key",
        provider_version=None,
        byte_hash="deadbeef",
        size_bytes=1024,
        custody_time=NOW,
        vault_path="sha256/de/deadbeef",
    )
    with pytest.raises(ValidationError):
        version.byte_hash = "changed"


def test_source_connection_never_holds_credential_value():
    conn = SourceConnection(
        id="c1",
        project_id="p1",
        provider="local_filesystem",
        root_path="/data/inbox",
        capabilities=["read"],
        credential_ref="secretref://vault/conn1",
    )
    assert conn.credential_ref == "secretref://vault/conn1"
    assert not hasattr(conn, "credential")


def test_source_snapshot_and_asset():
    snapshot = SourceSnapshot(
        id="s1",
        connection_id="c1",
        cursor=None,
        scan_time=NOW,
        completeness="full",
        manifest_hash="abc123",
        status="COMPLETE",
    )
    asset = Asset(
        id="a1",
        project_id="p1",
        snapshot_id=snapshot.id,
        logical_path="inbox/deed1.pdf",
        mime_type="application/pdf",
        created_at=NOW,
    )
    assert asset.snapshot_id == snapshot.id


def test_derived_artifact_and_evidence_span_frozen():
    artifact = DerivedArtifact(
        id="d1",
        parent_asset_version_ids=["av1"],
        recipe_version="1.0",
        artifact_type="ocr_text",
        vault_path="sha256/aa/aabbcc",
        byte_hash="aabbcc",
        created_at=NOW,
    )
    assert artifact.parent_asset_version_ids == ["av1"]

    span = EvidenceSpan(
        id="span1",
        asset_version_id="av1",
        page_or_sheet="1",
        row_or_region=None,
        text_excerpt="Grantor conveys all right, title, and interest",
        char_start=0,
        char_end=48,
        bbox_json=None,
        created_at=NOW,
    )
    with pytest.raises(ValidationError):
        span.text_excerpt = "mutated"


@pytest.mark.parametrize(
    "value_state",
    [
        "proved",
        "qualified",
        "assumed",
        "missing",
        "unknown",
        "inferred",
        "externally_researched",
    ],
)
def test_claim_value_state_enum(value_state):
    claim = Claim(
        id="claim1",
        project_id="p1",
        subject="Tract A",
        predicate="owned_by",
        value="Jane Doe",
        value_state=value_state,
        confidence=0.9,
        source_span_ids=["span1"],
        created_at=NOW,
    )
    assert claim.value_state == value_state


def test_claim_confidence_bounds():
    with pytest.raises(ValidationError):
        Claim(
            id="claim2",
            project_id="p1",
            subject="Tract A",
            predicate="owned_by",
            value="Jane Doe",
            value_state="proved",
            confidence=1.5,
            source_span_ids=[],
            created_at=NOW,
        )


def test_claim_invalid_value_state_rejected():
    with pytest.raises(ValidationError):
        Claim(
            id="claim3",
            project_id="p1",
            subject="Tract A",
            predicate="owned_by",
            value="Jane Doe",
            value_state="not_a_real_state",
            confidence=0.5,
            source_span_ids=[],
            created_at=NOW,
        )


def test_claim_support_and_conflict():
    support = ClaimSupport(
        id="cs1", claim_id="claim1", span_id="span1", support_rule_version="1.0"
    )
    assert support.claim_id == "claim1"

    conflict = Conflict(
        id="conf1",
        project_id="p1",
        claim_ids=["claim1", "claim2"],
        materiality="high",
        resolution_note=None,
        resolved_by=None,
        resolved_at=None,
    )
    assert conflict.materiality == "high"


def test_workflow_run_task_chain():
    workflow = WorkflowDefinition(
        id="wf1", name="title_exam", version="1.0", description="Title exam workflow"
    )
    run = Run(
        id="run1",
        workflow_id=workflow.id,
        project_id="p1",
        status="RUNNING",
        started_at=NOW,
        completed_at=None,
        metadata_json=None,
    )
    task = Task(
        id="t1",
        run_id=run.id,
        name="ocr_page",
        status="PLANNED",
        worker_type="ocr",
        input_json="{}",
        output_json=None,
        created_at=NOW,
        updated_at=NOW,
        lease_expires_at=None,
        attempt_count=0,
    )
    assert task.status == "PLANNED"
    task.status = "READY"
    assert task.status == "READY"

    dep = TaskDependency(upstream_task_id="t0", downstream_task_id="t1")
    assert dep.upstream_task_id == "t0"

    attempt = TaskAttempt(id="ta1", task_id="t1", started_at=NOW)
    assert attempt.completed_at is None

    lease = TaskLease(
        id="lease1",
        task_id="t1",
        worker_id="worker1",
        granted_at=NOW,
        expires_at=NOW,
        heartbeat_at=None,
    )
    assert lease.worker_id == "worker1"


def test_worker_capability_and_review_flow():
    capability = WorkerCapability(
        id="wc1",
        worker_type="ocr",
        capability="text_extraction",
        version="1.0",
        description="Extracts text from scanned images",
    )
    assert capability.capability == "text_extraction"

    gate = ReviewGate(
        id="rg1",
        task_id="t1",
        gate_type="examiner_review",
        required_role="examiner",
        prompt_for_reviewer="Confirm chain of title is complete",
    )
    decision = ReviewDecision(
        id="rd1",
        gate_id=gate.id,
        reviewer="jane.examiner",
        decision="approved",
        note=None,
        decided_at=NOW,
    )
    approval = Approval(
        id="appr1",
        gate_id=gate.id,
        decision_id=decision.id,
        artifact_hash="abc123",
        artifact_type="title_report",
        approved_by="jane.examiner",
        approved_at=NOW,
        expires_at=None,
    )
    assert approval.artifact_hash == "abc123"
    with pytest.raises(ValidationError):
        decision.decision = "rejected"  # ReviewDecision is frozen


def test_model_route_decision_and_tool_definition():
    route = ModelRouteDecision(
        id="mrd1",
        task_id="t1",
        provider="local",
        model_name="local-ocr-v1",
        reason="local_only_policy",
        input_hash="abc123",
        created_at=NOW,
    )
    assert route.provider == "local"

    tool = ToolDefinition(
        id="tool1",
        name="pdf_ocr",
        version="1.0",
        description="OCR tool",
        schema_json="{}",
        max_privilege_level="read_only",
    )
    assert tool.max_privilege_level == "read_only"

    tool_run = ToolRun(
        id="tr1",
        task_id="t1",
        tool_id=tool.id,
        input_hash="in123",
        output_hash=None,
        started_at=NOW,
        completed_at=None,
        status="RUNNING",
    )
    assert tool_run.status == "RUNNING"


def test_audit_event_is_frozen():
    event = AuditEvent(
        id="ae1",
        event_type="task.completed",
        actor="worker1",
        project_id="p1",
        task_id="t1",
        artifact_hash=None,
        payload_json=None,
        occurred_at=NOW,
    )
    with pytest.raises(ValidationError):
        event.event_type = "mutated"


def test_title_project_extends_project():
    title_project = TitleProject(
        id="tp1",
        name="Section 32 Title",
        jurisdiction="Windsor County",
        policy_set="default",
        confidentiality="internal",
        lifecycle_state="DRAFT",
        created_at=NOW,
        updated_at=NOW,
        section="32",
        township="10N",
        range="5W",
        county="Windsor",
        state="CO",
        search_from_date=None,
        search_to_date=None,
    )
    assert title_project.section == "32"
    assert isinstance(title_project, Project)


def test_jurisdiction_and_tract():
    jurisdiction = Jurisdiction(
        id="j1", state="CO", county="Windsor", search_standards_url=None
    )
    assert jurisdiction.state == "CO"

    tract = Tract(
        id="tr1",
        project_id="p1",
        label="Tract A",
        legal_description="NE/4 of Section 32",
        gross_acres_numerator=160,
        gross_acres_denominator=1,
    )
    assert tract.gross_acres_numerator == 160


def test_instrument_and_parties():
    instrument = Instrument(
        id="i1",
        project_id="p1",
        asset_version_id="av1",
        instrument_type="warranty_deed",
        effective_date=NOW,
        execution_date=NOW,
        recording_date=NOW,
        book="100",
        page="200",
        instrument_no="2024-001",
        county="Windsor",
        state="CO",
    )
    party = InstrumentParty(
        id="ip1",
        instrument_id=instrument.id,
        role="grantor",
        name="John Smith",
        normalized_name="SMITH, JOHN",
    )
    assert party.role == "grantor"

    recording_ref = RecordingReference(
        id="rr1",
        instrument_id=instrument.id,
        book="100",
        page="200",
        county="Windsor",
        state="CO",
        recording_date=NOW,
    )
    assert recording_ref.book == "100"

    link = ChainLink(
        id="cl1",
        project_id="p1",
        from_party="John Smith",
        to_party="Jane Doe",
        instrument_id=instrument.id,
        link_type="conveyance",
        tract_id="tr1",
        effective_date=NOW,
    )
    assert link.link_type == "conveyance"


def test_interest_ledger_entry_as_decimal():
    entry = InterestLedgerEntry(
        id="ile1",
        project_id="p1",
        tract_id="tr1",
        instrument_id="i1",
        interest_type="NRI",
        numerator=1,
        denominator=8,
        as_of_date=None,
        notes=None,
    )
    assert entry.as_decimal == pytest.approx(0.125)


def test_interest_ledger_entry_exact_fraction_not_float():
    entry = InterestLedgerEntry(
        id="ile2",
        project_id="p1",
        tract_id="tr1",
        instrument_id="i1",
        interest_type="WI",
        numerator=1,
        denominator=3,
        as_of_date=None,
        notes=None,
    )
    # numerator/denominator preserved exactly as ints, not collapsed to float
    assert entry.numerator == 1
    assert entry.denominator == 3
    assert entry.as_decimal == pytest.approx(1 / 3)


def test_title_exception_and_curative_item():
    exception = TitleException(
        id="te1",
        project_id="p1",
        exception_type="missing_release",
        description="Mortgage release not found",
        instruments_affected=["i1"],
        severity="material",
        status="open",
    )
    assert exception.severity == "material"

    curative = CurativeItem(
        id="ci1",
        exception_id=exception.id,
        action_required="Obtain release of mortgage",
        assigned_to=None,
        due_date=None,
        status="open",
    )
    assert curative.status == "open"


def test_workbook_candidate():
    candidate = WorkbookCandidate(
        id="wbc1",
        project_id="p1",
        asset_version_id="av1",
        candidate_label="v1",
        structural_score=0.95,
        evidence_score=0.9,
        selected=False,
        selected_by=None,
        selected_at=None,
        superseded_by=None,
    )
    assert candidate.selected is False
    candidate.selected = True
    assert candidate.selected is True
