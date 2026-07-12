"""Control-plane tests using only synthetic, fictional data."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from databossx import approval
from databossx.approval import ApprovalVerifier
from databossx.control_plane import ControlPlane, PromotionError

PROJECT_ID = "SYNTHETIC-DEMO-001"
KEY_ID = "demo-authority-1"

SYNTHETIC_MANIFEST = {
    "project_id": PROJECT_ID,
    "client": "Example Client Co. (SYNTHETIC)",
    "jurisdiction": "State of Example",
    "county": "Fictional County",
    "section": "00",
    "township": "00N",
    "range": "00W",
    "required_checks": ["ownership_totals"],
    "release_policy": {
        "technical_verification_is_not_release": True,
        "approved_hash_required": True,
        "human_gate": "G7",
    },
}


@pytest.fixture()
def keypair():
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


@pytest.fixture()
def verifier(keypair):
    _, public_pem = keypair
    return ApprovalVerifier({KEY_ID: {"public_key_pem": public_pem.decode()}})


@pytest.fixture()
def control(tmp_path: Path, verifier) -> ControlPlane:
    instance = ControlPlane(
        tmp_path / "control.sqlite3",
        intake_roots=[tmp_path],
        approval_verifier=verifier,
    )
    instance.initialize()
    instance.create_project(dict(SYNTHETIC_MANIFEST))
    return instance


def _mint(
    private_pem: bytes,
    *,
    project_id: str,
    asset_id: str,
    asset_sha256: str,
    from_state: str,
    to_state: str,
    nonce: str,
    subject: str = "examiner@example.com",
    ttl_seconds: int = 3600,
    issued_delta_seconds: int = 0,
) -> dict:
    issued = datetime.now(timezone.utc) + timedelta(seconds=issued_delta_seconds)
    payload = {
        "schema": approval.APPROVAL_SCHEMA,
        "key_id": KEY_ID,
        "project_id": project_id,
        "asset_id": asset_id,
        "asset_sha256": asset_sha256,
        "from_state": from_state,
        "to_state": to_state,
        "subject": subject,
        "scope": f"promote:{to_state}",
        "nonce": nonce,
        "issued_at": issued.isoformat(),
        "expires_at": (issued + timedelta(seconds=ttl_seconds)).isoformat(),
    }
    return approval.sign_payload(private_pem, payload)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _advance_to_qa(control: ControlPlane, tmp_path: Path):
    """Run the full pipeline up to (and including) the QA state."""
    output = tmp_path / "example_workbook.xlsx"
    output.write_bytes(b"synthetic workbook bytes")
    asset_sha = _sha(output)
    asset_id = f"asset:{asset_sha}"

    asset_ids, revision_id = control.intake_assets(
        PROJECT_ID, [output], source_authority=5, role="deliverable"
    )
    assert asset_ids == [asset_id]

    evidence_id = control.record_evidence(
        project_id=PROJECT_ID,
        asset_id=asset_id,
        locator="Title!M122",
        extracted_text="40.00 net mineral acres",
        conclusion="Ownership totals reconcile to 40.00",
        confidence={"extraction": 1.0, "calculation": 1.0},
    )
    run_id = control.start_run(
        project_id=PROJECT_ID,
        manifest_revision_id=revision_id,
        agent="calc-agent",
        model="deterministic",
        prompt_version="v1",
    )
    control.finish_run(run_id, status="SUCCEEDED", output_asset_ids=[asset_id])
    control.record_qa(
        project_id=PROJECT_ID,
        run_id=run_id,
        subject_id=asset_id,
        check_name="ownership_totals",
        severity="error",
        passed=True,
        detail="totals reconcile",
        evidence_ids=[evidence_id],
    )
    for state in ("STAGING", "EXTRACTED", "RECONCILED", "QA"):
        control.promote(
            project_id=PROJECT_ID,
            asset_id=asset_id,
            to_state=state,
            actor="pipeline",
            reason=f"completed {state.lower()}",
        )
    return asset_id, asset_sha


def test_ingest_is_content_addressed_and_preserves_locations(control, tmp_path):
    first = tmp_path / "instrument.txt"
    second = tmp_path / "copy.txt"
    first.write_bytes(b"synthetic recorded instrument")
    second.write_bytes(first.read_bytes())

    first_id = control.ingest_asset(PROJECT_ID, first, source_authority=1)
    second_id = control.ingest_asset(PROJECT_ID, second, source_authority=2)

    assert first_id == second_id
    assert first.read_bytes() == b"synthetic recorded instrument"
    with control.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM asset_locations").fetchone()[0] == 2


def test_intake_carries_manifest_policy_forward(control, tmp_path):
    source = tmp_path / "deed.txt"
    source.write_text("synthetic deed", encoding="utf-8")
    asset_ids, revision_id = control.intake_assets(
        PROJECT_ID, [source], source_authority=1
    )
    with control.connect() as connection:
        payload = json.loads(
            connection.execute(
                "SELECT payload_json FROM manifest_revisions WHERE id = ?", (revision_id,)
            ).fetchone()[0]
        )
    # The authoritative policy survives intake, and the asset IDs are added.
    assert payload["required_checks"] == ["ownership_totals"]
    assert payload["release_policy"]["human_gate"] == "G7"
    assert payload["asset_ids"] == asset_ids


def test_manifest_and_evidence_are_immutable(control, tmp_path):
    source = tmp_path / "deed.txt"
    source.write_text("Synthetic Book 00 Page 00", encoding="utf-8")
    asset_ids, _ = control.intake_assets(PROJECT_ID, [source], source_authority=1)
    evidence_id = control.record_evidence(
        project_id=PROJECT_ID,
        asset_id=asset_ids[0],
        locator="page 1",
        citation="Synthetic Book 00/Page 00",
        extracted_text="conveys an undivided 1/2 mineral interest",
        conclusion="Grantor conveyed 1/2 mineral interest",
        confidence={"extraction": 0.98},
    )
    with control.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE evidence SET conclusion = 'changed' WHERE id = ?", (evidence_id,)
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE manifest_revisions SET version = 99 WHERE project_id = ?",
                (PROJECT_ID,),
            )


def test_end_to_end_lifecycle_with_authenticated_approval(control, tmp_path, keypair):
    private_pem, _ = keypair
    asset_id, asset_sha = _advance_to_qa(control, tmp_path)

    # An agent cannot self-approve without a signed record.
    with pytest.raises(PromotionError, match="signed approval record"):
        control.promote(
            project_id=PROJECT_ID,
            asset_id=asset_id,
            to_state="APPROVED",
            actor="agent",
            reason="agent approval prohibited",
        )

    approve_token = _mint(
        private_pem,
        project_id=PROJECT_ID,
        asset_id=asset_id,
        asset_sha256=asset_sha,
        from_state="QA",
        to_state="APPROVED",
        nonce=str(uuid.uuid4()),
    )
    control.promote(
        project_id=PROJECT_ID,
        asset_id=asset_id,
        to_state="APPROVED",
        actor="examiner@example.com",
        reason="examiner reviewed evidence, math, and format",
        approval=approve_token,
    )

    deliver_token = _mint(
        private_pem,
        project_id=PROJECT_ID,
        asset_id=asset_id,
        asset_sha256=asset_sha,
        from_state="APPROVED",
        to_state="DELIVERED",
        nonce=str(uuid.uuid4()),
    )
    control.promote(
        project_id=PROJECT_ID,
        asset_id=asset_id,
        to_state="DELIVERED",
        actor="examiner@example.com",
        reason="release receipt signed",
        approval=deliver_token,
    )

    report = control.verify_ledger(PROJECT_ID)
    assert report["ok"], report["issues"]
    assert report["promotions"] == 6


def test_approval_replay_is_rejected(control, tmp_path, keypair):
    private_pem, _ = keypair
    asset_id, asset_sha = _advance_to_qa(control, tmp_path)
    nonce = str(uuid.uuid4())
    token = _mint(
        private_pem,
        project_id=PROJECT_ID,
        asset_id=asset_id,
        asset_sha256=asset_sha,
        from_state="QA",
        to_state="APPROVED",
        nonce=nonce,
    )
    control.promote(
        project_id=PROJECT_ID, asset_id=asset_id, to_state="APPROVED",
        actor="examiner@example.com", reason="first approval", approval=token,
    )
    # Re-using the same nonce/token to try to promote again is a replay.
    replay = _mint(
        private_pem,
        project_id=PROJECT_ID,
        asset_id=asset_id,
        asset_sha256=asset_sha,
        from_state="APPROVED",
        to_state="DELIVERED",
        nonce=nonce,
    )
    with pytest.raises(PromotionError, match="replay"):
        control.promote(
            project_id=PROJECT_ID, asset_id=asset_id, to_state="DELIVERED",
            actor="examiner@example.com", reason="replay attempt", approval=replay,
        )


def test_expired_approval_is_rejected(control, tmp_path, keypair):
    private_pem, _ = keypair
    asset_id, asset_sha = _advance_to_qa(control, tmp_path)
    token = _mint(
        private_pem,
        project_id=PROJECT_ID,
        asset_id=asset_id,
        asset_sha256=asset_sha,
        from_state="QA",
        to_state="APPROVED",
        nonce=str(uuid.uuid4()),
        ttl_seconds=3600,
        issued_delta_seconds=-7200,
    )
    with pytest.raises(PromotionError, match="expired"):
        control.promote(
            project_id=PROJECT_ID, asset_id=asset_id, to_state="APPROVED",
            actor="examiner@example.com", reason="expired", approval=token,
        )


def test_wrong_asset_hash_approval_is_rejected(control, tmp_path, keypair):
    private_pem, _ = keypair
    asset_id, _ = _advance_to_qa(control, tmp_path)
    token = _mint(
        private_pem,
        project_id=PROJECT_ID,
        asset_id=asset_id,
        asset_sha256="0" * 64,  # not the real content hash
        from_state="QA",
        to_state="APPROVED",
        nonce=str(uuid.uuid4()),
    )
    with pytest.raises(PromotionError, match="different asset content hash"):
        control.promote(
            project_id=PROJECT_ID, asset_id=asset_id, to_state="APPROVED",
            actor="examiner@example.com", reason="wrong asset", approval=token,
        )


def test_wrong_target_state_approval_is_rejected(control, tmp_path, keypair):
    private_pem, _ = keypair
    asset_id, asset_sha = _advance_to_qa(control, tmp_path)
    token = _mint(
        private_pem,
        project_id=PROJECT_ID,
        asset_id=asset_id,
        asset_sha256=asset_sha,
        from_state="QA",
        to_state="DELIVERED",  # signed for DELIVERED, presented for APPROVED
        nonce=str(uuid.uuid4()),
    )
    with pytest.raises(PromotionError, match="different target state"):
        control.promote(
            project_id=PROJECT_ID, asset_id=asset_id, to_state="APPROVED",
            actor="examiner@example.com", reason="wrong state", approval=token,
        )


def test_tampered_approval_signature_is_rejected(control, tmp_path, keypair):
    private_pem, _ = keypair
    asset_id, asset_sha = _advance_to_qa(control, tmp_path)
    token = _mint(
        private_pem,
        project_id=PROJECT_ID,
        asset_id=asset_id,
        asset_sha256=asset_sha,
        from_state="QA",
        to_state="APPROVED",
        nonce=str(uuid.uuid4()),
    )
    token["subject"] = "attacker@example.com"  # mutate a signed field
    with pytest.raises(PromotionError, match="signature verification failed"):
        control.promote(
            project_id=PROJECT_ID, asset_id=asset_id, to_state="APPROVED",
            actor="attacker@example.com", reason="tampered", approval=token,
        )


def test_approval_fails_closed_without_verifier(tmp_path):
    control = ControlPlane(
        tmp_path / "c.sqlite3", intake_roots=[tmp_path], approval_verifier=None
    )
    control.initialize()
    control.create_project(dict(SYNTHETIC_MANIFEST))
    asset_id, asset_sha = _advance_to_qa(control, tmp_path)
    with pytest.raises(PromotionError, match="no trusted approval verifier"):
        control.promote(
            project_id=PROJECT_ID, asset_id=asset_id, to_state="APPROVED",
            actor="examiner@example.com", reason="no verifier",
            approval={"schema": approval.APPROVAL_SCHEMA},
        )


def test_ledger_detects_direct_state_edit(control, tmp_path, keypair):
    private_pem, _ = keypair
    asset_id, asset_sha = _advance_to_qa(control, tmp_path)
    control.promote(
        project_id=PROJECT_ID, asset_id=asset_id, to_state="APPROVED",
        actor="examiner@example.com", reason="approved",
        approval=_mint(
            private_pem, project_id=PROJECT_ID, asset_id=asset_id,
            asset_sha256=asset_sha, from_state="QA", to_state="APPROVED",
            nonce=str(uuid.uuid4()),
        ),
    )
    assert control.verify_ledger(PROJECT_ID)["ok"]
    # Directly editing the state (bypassing promotions) is detected.
    with control.connect() as connection:
        connection.execute(
            "UPDATE asset_states SET state = 'DELIVERED' WHERE asset_id = ?", (asset_id,)
        )
    report = control.verify_ledger(PROJECT_ID)
    assert not report["ok"]
    assert any("direct state edit" in issue for issue in report["issues"])


def test_ledger_detects_forged_receipt_fields(control, tmp_path):
    asset_id, _ = _advance_to_qa(control, tmp_path)
    # Insert a promotion row with fields that do not match its receipt hash.
    with control.connect() as connection:
        connection.execute(
            """INSERT INTO promotions(
                   id, project_id, asset_id, from_state, to_state, actor, reason,
                   approval_id, previous_hash, receipt_hash, created_at
               ) VALUES (?, ?, ?, 'QA', 'APPROVED', 'attacker', 'forged',
                         NULL, NULL, 'not-a-real-hash', ?)""",
            (f"promotion:{uuid.uuid4()}", PROJECT_ID, asset_id,
             datetime.now(timezone.utc).isoformat()),
        )
    report = control.verify_ledger(PROJECT_ID)
    assert not report["ok"]
    assert any("hash mismatch" in issue for issue in report["issues"])


def test_ledger_detects_forged_approval(control, tmp_path, keypair):
    """An approval whose signature does not verify is flagged as invalid."""
    private_pem, _ = keypair
    asset_id, asset_sha = _advance_to_qa(control, tmp_path)
    # Forge an approvals row (valid-looking token, but signature won't verify).
    forged = _mint(
        private_pem, project_id=PROJECT_ID, asset_id=asset_id,
        asset_sha256=asset_sha, from_state="QA", to_state="APPROVED",
        nonce=str(uuid.uuid4()),
    )
    forged["asset_sha256"] = "1" * 64  # tamper after signing
    approval_id = f"approval:{uuid.uuid4()}"
    with control.connect() as connection:
        connection.execute(
            """INSERT INTO approvals(
                   id, project_id, asset_id, nonce, key_id, subject, from_state,
                   to_state, asset_sha256, scope, issued_at, expires_at, token_json, used_at
               ) VALUES (?, ?, ?, ?, ?, 'attacker', 'QA', 'APPROVED', ?, 'promote:APPROVED',
                         ?, ?, ?, ?)""",
            (
                approval_id, PROJECT_ID, asset_id, str(uuid.uuid4()), KEY_ID,
                "1" * 64, forged["issued_at"], forged["expires_at"],
                json.dumps(forged), datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.execute(
            """INSERT INTO promotions(
                   id, project_id, asset_id, from_state, to_state, actor, reason,
                   approval_id, previous_hash, receipt_hash, created_at
               ) VALUES (?, ?, ?, 'QA', 'APPROVED', 'attacker', 'forged approval',
                         ?, ?, ?, ?)""",
            (
                f"promotion:{uuid.uuid4()}", PROJECT_ID, asset_id, approval_id,
                None, f"forged-{uuid.uuid4()}",
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    report = control.verify_ledger(PROJECT_ID)
    assert not report["ok"]
    assert any("invalid" in issue for issue in report["issues"])


def test_classification_never_downgraded_across_projects(control, tmp_path):
    # Register the same content in a stricter project, then a permissive one.
    control.create_project(
        {
            "project_id": "SYNTHETIC-DEMO-002",
            "jurisdiction": "State of Example",
            "county": "Fictional County",
            "section": "01",
        }
    )
    shared = tmp_path / "shared.txt"
    shared.write_bytes(b"identical synthetic content")
    control.ingest_asset(
        PROJECT_ID, shared, source_authority=1, security_classification="RESTRICTED"
    )
    asset_id = control.ingest_asset(
        "SYNTHETIC-DEMO-002", shared, source_authority=1,
        security_classification="INTERNAL",
    )
    with control.connect() as connection:
        effective = connection.execute(
            "SELECT security_classification FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()[0]
    # Effective classification stays at the strictest ever seen.
    assert effective == "RESTRICTED"


def test_intake_rejects_path_outside_authorized_root(control, tmp_path):
    outside = tmp_path.parent / f"outside-{uuid.uuid4().hex}.txt"
    outside.write_bytes(b"synthetic")
    try:
        with pytest.raises(Exception) as excinfo:
            control.ingest_asset(PROJECT_ID, outside, source_authority=1)
        assert "outside" in str(excinfo.value).lower()
    finally:
        outside.unlink(missing_ok=True)


def test_run_parameters_and_errors_are_redacted(control, tmp_path):
    source = tmp_path / "in.txt"
    source.write_text("synthetic", encoding="utf-8")
    _, revision_id = control.intake_assets(PROJECT_ID, [source], source_authority=1)
    # Built by concatenation, and stored in neutrally named locals, so no
    # contiguous provider-token literal or credential-noun assignment lives in the
    # tracked source tree (the secret scanner would otherwise flag its own fixture).
    provider_sample = "sk-" + ("z" * 40)
    db_cred_sample = "p4ss" + ("w0rd" * 3)
    run_id = control.start_run(
        project_id=PROJECT_ID,
        manifest_revision_id=revision_id,
        agent="agent",
        model="model",
        prompt_version="v1",
        parameters={"api_key": provider_sample, "note": "ok"},
    )
    control.finish_run(
        run_id, status="FAILED",
        errors=[f"connect mongodb://user:{db_cred_sample}@host:27017/db failed"],
    )
    with control.connect() as connection:
        row = connection.execute(
            "SELECT parameters_json, errors_json FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
    assert provider_sample not in row["parameters_json"]
    assert "[REDACTED]" in row["parameters_json"]
    assert db_cred_sample not in row["errors_json"]


def test_initialize_creates_verified_backup(tmp_path):
    database = tmp_path / "control.sqlite3"
    control = ControlPlane(database, intake_roots=[tmp_path], approval_verifier=None)
    assert control.initialize() is None
    control.create_project(dict(SYNTHETIC_MANIFEST))
    backup = control.initialize()
    assert backup is not None
    assert backup.exists()
    with sqlite3.connect(backup) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
