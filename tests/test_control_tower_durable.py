"""Adversarial regression tests for issue #78 durable exactly-once controls."""

import os

import pytest

from control_tower.constants import (
    QUEUE_FOLDER_ID,
    RECEIPTS_FOLDER_ID,
    ClaimConflict,
    ControlTowerError,
    LeaseExpired,
    ReadbackMismatch,
)
from control_tower.drive import DriveOutage, OfflineDriveClient, SafeDriveWriter
from control_tower.durable import DurableStateStore
from control_tower.durable_runner import DurableGate0Runner
from control_tower.kernel import AppendOnlySpool, ClaimLedger, LeaseRegistry


SUCCESS = "S32_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY"
RETIRED = "DBX-S32-CONTAINMENT-TERMINALIZE-AND-CLEAN-AUTHORITY-COMPILE-20260801T1846CDT"


def make_stack(tmp_path, client=None):
    store = DurableStateStore(str(tmp_path / "state"))
    leases = LeaseRegistry(store=store)
    ledger = ClaimLedger(store=store)
    client = client or OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    writer = SafeDriveWriter(client, spool, leases=leases)
    runner = DurableGate0Runner(writer, ledger, leases)
    return store, leases, ledger, client, spool, writer, runner


def command(command_id="CMD-SUCCESSOR"):
    return {
        "id": "DRIVE-COMMAND-1",
        "parentId": QUEUE_FOLDER_ID,
        "title": "display text is not authority",
        "command_id": command_id,
    }


def test_claim_survives_restart_and_blocks_second_claimer(tmp_path):
    store = DurableStateStore(str(tmp_path / "state"))
    ClaimLedger(store=store).open("CMD|D|1", "writer-A", now=1.0)
    restarted = ClaimLedger(store=DurableStateStore(str(tmp_path / "state")))
    assert restarted.state("CMD|D|1")["state"] == "OPEN"
    with pytest.raises(ClaimConflict):
        restarted.open("CMD|D|1", "writer-B", now=2.0)


def test_retired_command_replay_is_denied_after_restart(tmp_path):
    root = str(tmp_path / "state")
    first = ClaimLedger(store=DurableStateStore(root))
    first.retire_command(RETIRED, evidence={"ruling": "spent"})
    restarted = ClaimLedger(store=DurableStateStore(root))
    with pytest.raises(ClaimConflict):
        restarted.prepare_open(RETIRED + "|DRIVE|9", "writer", 1.0, "start.json")


def test_fence_and_lease_are_monotonic_after_restart(tmp_path):
    root = str(tmp_path / "state")
    first_registry = LeaseRegistry(store=DurableStateStore(root))
    first = first_registry.acquire("scope", "writer-A", 0.0, 10.0)
    first_registry.release(first)
    restarted = LeaseRegistry(store=DurableStateStore(root))
    second = restarted.acquire("scope", "writer-B", 20.0, 10.0)
    assert second.fencing_sequence == first.fencing_sequence + 1
    assert restarted.require_valid(second, 21.0).holder == "writer-B"


def test_live_write_fails_without_registry_or_lease(tmp_path):
    class LiveClient(OfflineDriveClient):
        is_offline = False

    client = LiveClient()
    writer = SafeDriveWriter(client, AppendOnlySpool(str(tmp_path / "spool")))
    with pytest.raises(LeaseExpired):
        writer.emit_record(RECEIPTS_FOLDER_ID, "x.json", {"a": 1})

    store = DurableStateStore(str(tmp_path / "state"))
    leases = LeaseRegistry(store=store)
    writer = SafeDriveWriter(client, AppendOnlySpool(str(tmp_path / "spool2")), leases=leases)
    with pytest.raises(LeaseExpired):
        writer.emit_record(RECEIPTS_FOLDER_ID, "x.json", {"a": 1})


def test_pending_spool_recovers_after_outage(tmp_path):
    _store, leases, _ledger, client, _spool, writer, _runner = make_stack(tmp_path)
    lease = leases.acquire("section32", "writer", 0.0, 100.0)
    client.outage = True
    with pytest.raises(DriveOutage):
        writer.emit_record(
            RECEIPTS_FOLDER_ID, "pending.json", {"a": 1}, lease=lease, now=1.0
        )
    client.outage = False
    recovered = writer.recover_record(
        RECEIPTS_FOLDER_ID, "pending.json", lease=lease, now=2.0
    )
    assert recovered["byte_exact_match"] is True
    assert recovered["event"] == "UPLOAD_VERIFIED"
    assert len(client.find_all_by_name(RECEIPTS_FOLDER_ID, "pending.json")) == 1


def test_recovery_adopts_one_exact_existing_object(tmp_path):
    _store, leases, _ledger, client, spool, writer, _runner = make_stack(tmp_path)
    lease = leases.acquire("section32", "writer", 0.0, 100.0)
    client.outage = True
    with pytest.raises(DriveOutage):
        writer.emit_record(
            RECEIPTS_FOLDER_ID, "adopt.json", {"a": 1}, lease=lease, now=1.0
        )
    client.outage = False
    payload = spool.read_record("adopt.json")
    client.seed("EXTERNAL-WINNER", RECEIPTS_FOLDER_ID, "adopt.json", payload)
    result = writer.recover_record(
        RECEIPTS_FOLDER_ID, "adopt.json", lease=lease, now=2.0
    )
    assert result["drive_id"] == "EXTERNAL-WINNER"
    assert result["event"] == "UPLOAD_RECOVERED_EXACT_MATCH"


def test_recovery_rejects_duplicate_drive_objects(tmp_path):
    _store, leases, _ledger, client, spool, writer, _runner = make_stack(tmp_path)
    lease = leases.acquire("section32", "writer", 0.0, 100.0)
    spool.put_record("dup.json", b'{"hold":"FOR REVIEW - HOLD NO EXTERNAL RELEASE"}\n')
    payload = spool.read_record("dup.json")
    client.seed("DUP-1", RECEIPTS_FOLDER_ID, "dup.json", payload)
    client.seed("DUP-2", RECEIPTS_FOLDER_ID, "dup.json", payload)
    with pytest.raises(ControlTowerError):
        writer.recover_record(RECEIPTS_FOLDER_ID, "dup.json", lease=lease, now=1.0)


def test_start_claim_outage_resumes_without_second_claim(tmp_path):
    root = tmp_path
    _store, _leases, _ledger, client, _spool, _writer, runner = make_stack(root)
    client.outage = True
    with pytest.raises(DriveOutage):
        runner.claim(command(), 1, "writer", now=1.0, ttl_seconds=100)

    # Restart every stateful object and finish the same prepared claim.
    client.outage = False
    _store2, _leases2, ledger2, _client2, _spool2, _writer2, runner2 = make_stack(
        root, client=client
    )
    result = runner2.claim(command(), 1, "writer", now=2.0, ttl_seconds=100)
    assert result["claim"]["state"] == "OPEN"
    assert len(client.find_all_by_name(RECEIPTS_FOLDER_ID, result["prepared"]["start_receipt_name"])) == 1
    assert ledger2.state(result["claim_key"])["state"] == "OPEN"


def test_terminal_outage_leaves_prepared_and_recovers_after_restart(tmp_path):
    root = tmp_path
    _store, leases, ledger, client, _spool, _writer, runner = make_stack(root)
    claimed = runner.claim(command(), 1, "writer", now=1.0, ttl_seconds=100)
    lease = claimed["lease"]
    client.outage = True
    with pytest.raises(DriveOutage):
        runner.terminalize(claimed["claim_key"], SUCCESS, {"ok": True}, lease, now=2.0)
    assert ledger.state(claimed["claim_key"])["state"] == "TERMINAL_PREPARED"

    client.outage = False
    _store2, leases2, ledger2, _client2, _spool2, _writer2, runner2 = make_stack(
        root, client=client
    )
    durable_lease = leases2.require_valid(lease, 3.0)
    finished = runner2.terminalize(
        claimed["claim_key"], SUCCESS, {"ok": True}, durable_lease, now=3.0
    )
    assert finished["claim"]["state"] == "RESOLVED"
    assert ledger2.state(claimed["claim_key"])["state"] == "RESOLVED"


def test_terminal_uploaded_can_be_resolved_after_restart(tmp_path):
    root = str(tmp_path / "state")
    store = DurableStateStore(root)
    ledger = ClaimLedger(store=store)
    ledger.open("CMD|D|1", "writer", 0.0)
    ledger.prepare_terminal("CMD|D|1", SUCCESS, "terminal.json")
    ledger.mark_terminal_uploaded("CMD|D|1", "DRIVE-ID", "abc")
    restarted = ClaimLedger(store=DurableStateStore(root))
    assert restarted.resolve_terminal("CMD|D|1")["state"] == "RESOLVED"


def test_runner_rejects_mismatched_registry_sources(tmp_path):
    client = OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    first = DurableStateStore(str(tmp_path / "first"))
    second = DurableStateStore(str(tmp_path / "second"))
    leases = LeaseRegistry(store=first)
    writer = SafeDriveWriter(client, spool, leases=leases)
    with pytest.raises(ControlTowerError):
        DurableGate0Runner(writer, ClaimLedger(store=second), leases)


def test_existing_object_with_wrong_bytes_is_rejected(tmp_path):
    _store, leases, _ledger, client, spool, writer, _runner = make_stack(tmp_path)
    lease = leases.acquire("section32", "writer", 0.0, 100.0)
    client.outage = True
    with pytest.raises(DriveOutage):
        writer.emit_record(
            RECEIPTS_FOLDER_ID, "wrong.json", {"a": 1}, lease=lease, now=1.0
        )
    client.outage = False
    client.seed("WRONG", RECEIPTS_FOLDER_ID, "wrong.json", b"not the spooled bytes")
    with pytest.raises(ReadbackMismatch):
        writer.recover_record(RECEIPTS_FOLDER_ID, "wrong.json", lease=lease, now=2.0)
