"""Recovery must reject spool bytes not bound into durable claim state."""

import pytest

from control_tower.constants import QUEUE_FOLDER_ID, RECEIPTS_FOLDER_ID, ClaimConflict, ReadbackMismatch
from control_tower.drive import DriveOutage, OfflineDriveClient, SafeDriveWriter
from control_tower.durable import DurableStateStore
from control_tower.durable_runner import DurableGate0Runner
from control_tower.kernel import AppendOnlySpool, ClaimLedger, LeaseRegistry


SUCCESS = "S32_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY"
HOLD = "FOR REVIEW - HOLD NO EXTERNAL RELEASE"


def stack(tmp_path):
    store = DurableStateStore(str(tmp_path / "state"))
    leases = LeaseRegistry(store=store)
    ledger = ClaimLedger(store=store)
    client = OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    writer = SafeDriveWriter(client, spool, leases=leases)
    runner = DurableGate0Runner(writer, ledger, leases)
    return store, leases, ledger, client, spool, runner


def command():
    return {
        "id": "DRIVE-COMMAND",
        "parentId": QUEUE_FOLDER_ID,
        "title": "display only",
        "command_id": "CMD-SUCCESSOR",
    }


def overwrite_spool(spool, name):
    path = spool.root + "/" + name
    with open(path, "wb") as handle:
        handle.write((
            '{"hold":"%s","tampered":true}\n' % HOLD
        ).encode("utf-8"))


def test_changed_start_spool_is_rejected_after_restart(tmp_path):
    _store, _leases, ledger, client, spool, runner = stack(tmp_path)
    client.outage = True
    with pytest.raises(DriveOutage):
        runner.claim(command(), 1, "writer", now=1.0, ttl_seconds=100)

    key = "CMD-SUCCESSOR|DRIVE-COMMAND|1"
    name = ledger.state(key)["start_receipt_name"]
    overwrite_spool(spool, name)
    client.outage = False

    restarted_store = DurableStateStore(str(tmp_path / "state"))
    restarted_leases = LeaseRegistry(store=restarted_store)
    restarted_ledger = ClaimLedger(store=restarted_store)
    restarted_writer = SafeDriveWriter(
        client,
        AppendOnlySpool(str(tmp_path / "spool")),
        leases=restarted_leases,
    )
    restarted_runner = DurableGate0Runner(
        restarted_writer, restarted_ledger, restarted_leases
    )
    with pytest.raises(ReadbackMismatch):
        restarted_runner.claim(command(), 1, "writer", now=2.0, ttl_seconds=100)
    assert client.find_all_by_name(RECEIPTS_FOLDER_ID, name) == []


def test_changed_terminal_spool_is_rejected_after_restart(tmp_path):
    _store, _leases, ledger, client, spool, runner = stack(tmp_path)
    claimed = runner.claim(command(), 1, "writer", now=1.0, ttl_seconds=100)
    client.outage = True
    with pytest.raises(DriveOutage):
        runner.terminalize(
            claimed["claim_key"], SUCCESS, {"ok": True}, claimed["lease"], now=2.0
        )

    state = ledger.state(claimed["claim_key"])
    overwrite_spool(spool, state["terminal_name"])
    client.outage = False

    restarted_store = DurableStateStore(str(tmp_path / "state"))
    restarted_leases = LeaseRegistry(store=restarted_store)
    restarted_ledger = ClaimLedger(store=restarted_store)
    restarted_writer = SafeDriveWriter(
        client,
        AppendOnlySpool(str(tmp_path / "spool")),
        leases=restarted_leases,
    )
    restarted_runner = DurableGate0Runner(
        restarted_writer, restarted_ledger, restarted_leases
    )
    lease = restarted_leases.require_valid(claimed["lease"], 3.0)
    with pytest.raises(ReadbackMismatch):
        restarted_runner.terminalize(
            claimed["claim_key"], SUCCESS, {"ok": True}, lease, now=3.0
        )
    assert client.find_all_by_name(RECEIPTS_FOLDER_ID, state["terminal_name"]) == []


def test_changed_terminal_findings_conflict_with_bound_digest(tmp_path):
    _store, _leases, ledger, client, _spool, runner = stack(tmp_path)
    claimed = runner.claim(command(), 1, "writer", now=1.0, ttl_seconds=100)
    client.outage = True
    with pytest.raises(DriveOutage):
        runner.terminalize(
            claimed["claim_key"], SUCCESS, {"ok": True}, claimed["lease"], now=2.0
        )
    client.outage = False
    with pytest.raises(ClaimConflict):
        runner.terminalize(
            claimed["claim_key"], SUCCESS, {"ok": False}, claimed["lease"], now=3.0
        )
    assert ledger.state(claimed["claim_key"])["state"] == "TERMINAL_PREPARED"
