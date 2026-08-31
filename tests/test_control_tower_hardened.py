"""Comprehensive hardened tests for DataBossX Control Tower:
- Concurrency and race-condition defenses
- Adversarial inputs and spoofing attacks
- Drive outage, crash recovery, and state resumption
- State machine lifecycle enforcement
- Heartbeat and stale-writer rejection
- Monotonic fencing and lease expiration
- Emergency stop flag halts
- Output allowlist enforcement
- Exact credential redaction and token sanitization
"""

import concurrent.futures
import json
import os
import threading
import time

import pytest

from control_tower.audit import MISMATCH, OBSERVED, UNREACHABLE, audit_expected_file, run_audit
from control_tower.constants import (
    ALLOWED_READ_FOLDER_IDS,
    ALLOWED_WRITE_FOLDER_IDS,
    BLOCKED_FOLDER_ID,
    COMPLETED_FOLDER_ID,
    CONTROL_ROOT_FOLDER_ID,
    HOLD,
    HUMAN_APPROVAL_FOLDER_ID,
    MODE_MUTATION,
    MODE_READ_ONLY,
    POLLED_FOLDER_ID,
    QUEUE_FOLDER_ID,
    RECEIPTS_FOLDER_ID,
    RETIRED_GATE0_COMMAND_DRIVE_ID,
    RETIRED_GATE0_COMMAND_ID,
    SENTINEL_OWNER_DECISION,
    SENTINEL_REISSUE_BLOCKED,
    SENTINEL_SUCCESSOR_GATE0_CLEAN,
    SENTINEL_TERMINALIZED,
    STATUS_FOLDER_ID,
    V10_EXPECTED_SHA256,
    V11_EXPECTED_SHA256,
    V12_EXPECTED_SHA256,
    V13_WIP_EXPECTED_SHA256,
    WATCHER_OUTPUT_FOLDER_ID,
    AuthorityDenied,
    ClaimConflict,
    ControlTowerError,
    FencingViolation,
    HeartbeatExpired,
    HoldViolation,
    LeaseExpired,
    MutationDenied,
    OutputNotAllowed,
    ProtectedArtifactUpload,
    ReadbackMismatch,
    ReadDenied,
    RetiredCommandDenied,
    SpoolCollision,
    StateMachineViolation,
    StopFlagTriggered,
    UntrustedUrl,
    WriteDenied,
)
from control_tower.drive import DriveOutage, OfflineDriveClient, SafeDriveWriter
from control_tower.kernel import (
    AppendOnlySpool,
    ClaimLedger,
    FencingRegistry,
    HeartbeatRegistry,
    LeaseRegistry,
    StateMachine,
    StopFlag,
    TaskEnvelope,
    claim_key,
    derive_authority,
    require_mutation_allowed,
)
from control_tower.safety import (
    assert_active_command,
    assert_hold_intact,
    assert_output_allowed,
    assert_pollable,
    assert_read_allowed,
    assert_trusted_url,
    assert_uploadable,
    assert_write_allowed,
    canonical_drive_url,
    canonical_json_bytes,
    make_sha256_sidecar,
    redact,
    redact_tree,
    sha256_hex,
    stamp_hold,
    verify_readback,
)
from control_tower.tower import Gate0Runner, offline_canary, selftest


# ==========================================================================
# 1. CONCURRENCY & RACE-CONDITION DEFENSES
# ==========================================================================
def test_concurrent_claim_attempts_produce_single_winner():
    """When multiple workers attempt to claim the same command key concurrently,
    exactly one must win and all others must fail with ClaimConflict."""
    ledger = ClaimLedger()
    key = "CMD-CONCURRENT-1|DRIVE123|1"
    num_workers = 16
    results = []
    errors = []

    def try_claim(worker_id):
        try:
            res = ledger.open(key, f"worker-{worker_id}", now=100.0 + worker_id)
            results.append(res)
        except ClaimConflict as e:
            errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(try_claim, i) for i in range(num_workers)]
        concurrent.futures.wait(futures)

    assert len(results) == 1, "Exactly one worker must acquire the claim"
    assert len(errors) == num_workers - 1, "All other workers must receive ClaimConflict"
    assert ledger.state(key)["state"] == "OPEN"


def test_concurrent_spool_exclusive_creation_guarantees_collision_safety(tmp_path):
    """When multiple threads try to write a record with the same filename,
    exactly one must succeed and all others must raise SpoolCollision."""
    spool = AppendOnlySpool(str(tmp_path / "concurrent_spool"))
    record_name = "concurrent_record.json"
    num_threads = 12
    successes = []
    collisions = []

    def write_record(worker_id):
        payload = f'{{"worker": {worker_id}}}'.encode("utf-8")
        try:
            res = spool.put_record(record_name, payload)
            successes.append((worker_id, res))
        except SpoolCollision as e:
            collisions.append((worker_id, e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(write_record, i) for i in range(num_threads)]
        concurrent.futures.wait(futures)

    assert len(successes) == 1, "Exactly one put_record must succeed"
    assert len(collisions) == num_threads - 1, "All collisions must fail closed"
    winner_id, _ = successes[0]
    with open(os.path.join(spool.root, record_name), "rb") as f:
        content = json.loads(f.read().decode("utf-8"))
        assert content["worker"] == winner_id


def test_concurrent_fencing_token_advancement_strictly_monotonic():
    """Fencing registry sequence advancement under multi-threaded requests
    must be strictly increasing and collision-free."""
    fencing = FencingRegistry()
    scope = "section32_concurrency"
    num_requests = 100
    sequences = []
    lock = threading.Lock()

    def get_seq():
        with lock:
            seq = fencing.next_sequence(scope)
            sequences.append(seq)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(get_seq) for _ in range(num_requests)]
        concurrent.futures.wait(futures)

    assert len(sequences) == num_requests
    assert len(set(sequences)) == num_requests, "Every fencing sequence must be distinct"
    assert max(sequences) == num_requests
    assert fencing.highest(scope) == num_requests


# ==========================================================================
# 2. ADVERSARIAL INPUTS & SECURITY SPOOFING
# ==========================================================================
@pytest.mark.parametrize(
    "spoofed_id",
    [
        "../" * 5 + "etc/passwd",
        "../../root/.ssh/id_rsa",
        "https://evil.com/fake_doc",
        "1aLfAZdOvhAbBzg_pTluH12X4yoZ3u_JC/view",
        "short",
        "ID WITH SPACES AND INJECTION",
        "; rm -rf / ;",
        "<script>alert(1)</script>",
    ],
)
def test_adversarial_malformed_drive_ids_rejected(spoofed_id):
    """Malicious or non-standard Drive ID formats must be rejected before URL interpolation."""
    with pytest.raises(UntrustedUrl):
        canonical_drive_url(spoofed_id)


@pytest.mark.parametrize(
    "malicious_url",
    [
        "http://drive.google.com/file/d/1234567890/view",  # insecure http
        "https://drive.google.com.attacker.com/file/d/1234567890",
        "https://docichat.com/phish?token=secret",
        "https://livepolls.app/auth",
        "https://evil-drive.google.com/file/d/1234567890",
        "ftp://drive.google.com/file/d/1234567890",
        "javascript:alert(1)",
        "file:///etc/passwd",
    ],
)
def test_adversarial_url_spoofing_rejected(malicious_url):
    """Only exact trusted Google APIs and Docs HTTPS URLs are permitted."""
    with pytest.raises(UntrustedUrl):
        assert_trusted_url(malicious_url)


@pytest.mark.parametrize(
    "disguised_suffix,content",
    [
        ("report.json.xlsx", b'{"not":"json"}'),
        ("summary.pdf", b'%PDF-1.4'),
        ("evidence.zip", b'PK\x03\x04\x00\x00'),
        ("scan.tiff", b'II*\x00'),
        ("table.csv", b'a,b,c\n1,2,3'),
        ("document.docx", b'PK\x03\x04'),
    ],
)
def test_adversarial_file_upload_extensions_and_signatures_denied(disguised_suffix, content):
    """Payloads carrying binary document headers or prohibited extensions must fail closed."""
    with pytest.raises(ProtectedArtifactUpload):
        assert_uploadable(content, filename=disguised_suffix, mime_type="application/json")


def test_adversarial_zip_signature_smuggled_inside_json_denied():
    """Even if extension is .json and MIME is application/json, a PK header raises."""
    pk_payload = b"PK" + b"\x03\x04" + b'{"smuggled": "data"}'
    with pytest.raises(ProtectedArtifactUpload):
        assert_uploadable(pk_payload, filename="safe.json", mime_type="application/json")


def test_adversarial_protected_hash_payload_denied(monkeypatch):
    """Payload whose digest matches any pinned workbook baseline is refused."""
    fake_v12_bytes = b"EXACT_PROTECTED_WORKBOOK_BYTES"
    fake_hash = sha256_hex(fake_v12_bytes)
    monkeypatch.setattr(
        "control_tower.safety.PROTECTED_WORKBOOK_SHA256",
        frozenset({fake_hash, V12_EXPECTED_SHA256}),
    )
    with pytest.raises(ProtectedArtifactUpload):
        assert_uploadable(fake_v12_bytes, filename="control_record.json", mime_type="application/json")


# ==========================================================================
# 3. RETIRED COMMAND DEFENSES (OWNER RULING ENFORCEMENT)
# ==========================================================================
def test_retired_gate0_command_drive_id_fails_closed():
    """The original Gate 0 command Drive ID 1C0C8ERuCYm6Rqso0ahLXMifhXqlYjinOlFkN5k29NCE is spent."""
    with pytest.raises(RetiredCommandDenied):
        assert_active_command(RETIRED_GATE0_COMMAND_DRIVE_ID)


def test_retired_gate0_command_id_fails_closed():
    """The original Gate 0 command ID DBX-S32-CONTAINMENT-TERMINALIZE-AND-CLEAN-AUTHORITY-COMPILE-20260801T1846CDT is spent."""
    with pytest.raises(RetiredCommandDenied):
        assert_active_command("SOME_DRIVE_ID", RETIRED_GATE0_COMMAND_ID)


def test_derive_authority_refuses_spent_gate0_in_queue():
    """Even if placed in 01_QUEUED, the spent command cannot yield authority."""
    meta = {
        "id": RETIRED_GATE0_COMMAND_DRIVE_ID,
        "parentId": QUEUE_FOLDER_ID,
        "command_id": RETIRED_GATE0_COMMAND_ID,
        "title": "01_EXECUTE_NEXT__OLD_GATE0",
    }
    with pytest.raises(RetiredCommandDenied):
        derive_authority(meta)


# ==========================================================================
# 4. STATE MACHINE & LIFECYCLE CONTROLS
# ==========================================================================
def test_state_machine_valid_command_lifecycle():
    """Valid command progression: QUEUED -> CLAIMED -> AUDITING -> TERMINALIZED."""
    assert StateMachine.validate_command_transition("QUEUED", "CLAIMED") == "CLAIMED"
    assert StateMachine.validate_command_transition("CLAIMED", "AUDITING") == "AUDITING"
    assert StateMachine.validate_command_transition("AUDITING", "TERMINALIZED") == "TERMINALIZED"


@pytest.mark.parametrize(
    "from_st,to_st",
    [
        ("TERMINALIZED", "QUEUED"),
        ("TERMINALIZED", "CLAIMED"),
        ("TERMINALIZED", "AUDITING"),
        ("AUDITING", "CLAIMED"),
        ("QUEUED", "AUDITING"),
        ("UNKNOWN", "CLAIMED"),
    ],
)
def test_state_machine_illegal_command_transitions_refused(from_st, to_st):
    with pytest.raises(StateMachineViolation):
        StateMachine.validate_command_transition(from_st, to_st)


def test_state_machine_task_lifecycle():
    assert StateMachine.validate_task_transition("CREATED", "ACTIVATED") == "ACTIVATED"
    assert StateMachine.validate_task_transition("ACTIVATED", "IN_PROGRESS") == "IN_PROGRESS"
    assert StateMachine.validate_task_transition("IN_PROGRESS", "COMPLETED") == "COMPLETED"
    with pytest.raises(StateMachineViolation):
        StateMachine.validate_task_transition("COMPLETED", "IN_PROGRESS")


# ==========================================================================
# 5. HEARTBEATS, LEASE EXPIRATION & STALE WRITERS
# ==========================================================================
def test_heartbeat_tracking_and_expiry():
    registry = HeartbeatRegistry(default_timeout_seconds=30.0)
    lease_id = "LEASE-SCOPE-1"
    now = 1000.0

    registry.pulse(lease_id, now)
    assert registry.check(lease_id, now + 10.0) is True
    assert registry.check(lease_id, now + 29.9) is True

    with pytest.raises(HeartbeatExpired):
        registry.check(lease_id, now + 30.1)

    with pytest.raises(HeartbeatExpired):
        registry.check("UNKNOWN-LEASE", now)


def test_writer_heartbeat_pulse_during_emit(tmp_path):
    client = OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    fencing = FencingRegistry()
    leases = LeaseRegistry(fencing)
    heartbeats = HeartbeatRegistry(default_timeout_seconds=60.0)
    writer = SafeDriveWriter(client, spool, leases=leases, heartbeats=heartbeats)

    lease = leases.acquire("s32", "writer1", now=100.0, ttl_seconds=300.0)
    writer.emit_record(RECEIPTS_FOLDER_ID, "rec1.json", {"k": 1}, lease=lease, now=100.0)

    # Verify heartbeat was automatically pulsed
    assert heartbeats.check(lease.lease_id, 110.0) is True


# ==========================================================================
# 6. EMERGENCY STOP FLAG
# ==========================================================================
def test_emergency_stop_flag_in_memory():
    stop = StopFlag()
    assert stop.is_active() == (False, None)
    stop.require_not_stopped()

    stop.trigger("Immediate halt due to anomalous writer")
    assert stop.is_active()[0] is True
    with pytest.raises(StopFlagTriggered):
        stop.require_not_stopped()

    stop.clear()
    assert stop.is_active() == (False, None)
    stop.require_not_stopped()


def test_emergency_stop_flag_environment_variable(monkeypatch):
    stop = StopFlag()
    monkeypatch.setenv("DBX_EMERGENCY_STOP", "true")
    assert stop.is_active()[0] is True
    with pytest.raises(StopFlagTriggered):
        stop.require_not_stopped()


def test_emergency_stop_flag_halts_safedrivewriter(tmp_path):
    client = OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    stop = StopFlag()
    writer = SafeDriveWriter(client, spool, stop_flag=stop)

    stop.trigger("Safety hold")
    with pytest.raises(StopFlagTriggered):
        writer.poll_queue()

    with pytest.raises(StopFlagTriggered):
        writer.emit_record(RECEIPTS_FOLDER_ID, "blocked.json", {"a": 1})


# ==========================================================================
# 7. OUTPUT ALLOWLIST DEFENSES
# ==========================================================================
def test_output_allowlist_restriction():
    strict_allowlist = frozenset({RECEIPTS_FOLDER_ID, WATCHER_OUTPUT_FOLDER_ID})
    assert assert_output_allowed(RECEIPTS_FOLDER_ID, strict_allowlist) == RECEIPTS_FOLDER_ID
    assert assert_output_allowed(WATCHER_OUTPUT_FOLDER_ID, strict_allowlist) == WATCHER_OUTPUT_FOLDER_ID

    with pytest.raises(OutputNotAllowed):
        assert_output_allowed(STATUS_FOLDER_ID, strict_allowlist)

    with pytest.raises(OutputNotAllowed):
        assert_output_allowed("1UNAPPROVED_FOLDER_ID", strict_allowlist)


# ==========================================================================
# 8. SIDECAR GENERATION & INTEGRITY
# ==========================================================================
def test_make_sha256_sidecar_format():
    payload = b'{"hello": "world"}\n'
    sidecar_text = make_sha256_sidecar("receipt_01.json", payload)
    expected_digest = sha256_hex(payload)
    assert sidecar_text == f"{expected_digest}  receipt_01.json\n"


def test_emit_record_with_sidecar_spools_and_uploads_both(tmp_path):
    client = OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    writer = SafeDriveWriter(client, spool)

    record = {"result": "PASS", "details": "Gate 0 verified"}
    res = writer.emit_record_with_sidecar(RECEIPTS_FOLDER_ID, "terminal_receipt.json", record)

    assert res["byte_exact_match"] is True
    assert "sidecar" in res
    sidecar_res = res["sidecar"]
    assert sidecar_res["byte_exact_match"] is True
    assert sidecar_res["name"] == "terminal_receipt.json.sha256"

    # Verify both files exist in spool
    assert os.path.exists(os.path.join(spool.root, "terminal_receipt.json"))
    assert os.path.exists(os.path.join(spool.root, "terminal_receipt.json.sha256"))


# ==========================================================================
# 9. DURABLE SPOOL CRASH RECOVERY & ROLLBACK
# ==========================================================================
def test_spool_outage_recovery_flow(tmp_path):
    client = OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    writer = SafeDriveWriter(client, spool)

    client.outage = True
    with pytest.raises(DriveOutage):
        writer.emit_record(RECEIPTS_FOLDER_ID, "pending_report.json", {"step": 1})

    pending = spool.get_pending_uploads()
    assert len(pending) == 1
    assert pending[0]["name"] == "pending_report.json"

    # Bring client back online and recover
    client.outage = False
    recovered = writer.recover_pending_uploads()
    assert len(recovered) == 1
    assert recovered[0]["byte_exact_match"] is True
    assert recovered[0]["recovered_from_outage"] is True

    # After recovery, no pending items remain
    assert spool.get_pending_uploads() == []


def test_spool_rollback_recording(tmp_path):
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    spool.rollback("partial_run_01.json", "Network connection reset before verification")

    journal = spool.read_journal()
    assert len(journal) == 1
    entry = journal[0]
    assert entry["event"] == "ROLLBACK_RECORDED"
    assert entry["record_name"] == "partial_run_01.json"
    assert entry["hold"] == HOLD


# ==========================================================================
# 10. SUCCESSOR GATE 0 RUNNER INTEGRATION
# ==========================================================================
def test_gate0_runner_clean_successor_round_trip(tmp_path):
    client = OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    fencing = FencingRegistry()
    leases = LeaseRegistry(fencing)
    heartbeats = HeartbeatRegistry()
    stop = StopFlag()
    writer = SafeDriveWriter(
        client, spool, leases=leases, heartbeats=heartbeats, stop_flag=stop
    )
    runner = Gate0Runner(writer, leases=leases, heartbeats=heartbeats, stop_flag=stop)

    # Seed clean successor command in queue
    cmd_meta = {
        "id": "1VfdAVRX8zG8Elzi_ucsOkM-Gy27JHrH_pitfg9oLY3E",
        "parentId": QUEUE_FOLDER_ID,
        "command_id": "DBX-CMD-S32-GATE0-SUCCESSOR-20260802T1300CDT",
        "title": "01_EXECUTE_NEXT__SUCCESSOR_GATE0",
    }
    client.seed(cmd_meta["id"], QUEUE_FOLDER_ID, cmd_meta["title"])

    # 1. Preflight
    pre = runner.preflight()
    assert pre["ok"] is True

    # 2. Claim
    claimed = runner.claim(cmd_meta, command_revision=1, holder="windows-codex-lane", now=1000.0)
    assert claimed["receipt"]["byte_exact_match"] is True
    assert "sidecar" in claimed["receipt"]

    # 3. Read-only audit
    audit = runner.execute_read_only(repo_path=str(tmp_path))
    assert audit["workbook_opened"] is False
    assert audit["workbook_mutated"] is False

    # 4. Terminalize with successor clean sentinel
    term = runner.terminalize(
        claimed["claim_key"],
        SENTINEL_SUCCESSOR_GATE0_CLEAN,
        findings={"audit_completeness": audit["audit_completeness"]},
        lease=claimed["lease"],
        now=1050.0,
    )
    assert term["receipt"]["byte_exact_match"] is True
    assert "sidecar" in term["receipt"]
    assert term["claim"]["state"] == "RESOLVED"
    assert term["claim"]["sentinel"] == SENTINEL_SUCCESSOR_GATE0_CLEAN
