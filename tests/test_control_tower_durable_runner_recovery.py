"""Runner-level recovery for the final crash window in issue #78."""

from control_tower.constants import QUEUE_FOLDER_ID, RECEIPTS_FOLDER_ID
from control_tower.drive import OfflineDriveClient, SafeDriveWriter
from control_tower.durable import DurableStateStore
from control_tower.durable_runner import DurableGate0Runner
from control_tower.kernel import AppendOnlySpool, ClaimLedger, LeaseRegistry
from control_tower.safety import canonical_json_bytes, stamp_hold


SUCCESS = "S32_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY"


def test_runner_recovers_terminal_uploaded_before_local_resolution(tmp_path):
    state_root = str(tmp_path / "state")
    spool_root = str(tmp_path / "spool")
    client = OfflineDriveClient()

    store = DurableStateStore(state_root)
    leases = LeaseRegistry(store=store)
    ledger = ClaimLedger(store=store)
    spool = AppendOnlySpool(spool_root)
    writer = SafeDriveWriter(client, spool, leases=leases)
    runner = DurableGate0Runner(writer, ledger, leases)

    command = {
        "id": "DRIVE-COMMAND",
        "parentId": QUEUE_FOLDER_ID,
        "title": "display only",
        "command_id": "CMD-SUCCESSOR",
    }
    claimed = runner.claim(command, 1, "writer", now=1.0, ttl_seconds=100)
    key = claimed["claim_key"]
    lease = claimed["lease"]
    terminal_name = "DBX_RECEIPT__GATE0_TERMINAL__{0}.json".format(
        key.replace("|", "__")
    )
    terminal = stamp_hold(
        {
            "schema": "databossx.gate0_terminal.v2",
            "receipt_type": "GATE0_TERMINAL",
            "claim_key": key,
            "terminal_sentinel": SUCCESS,
            "findings": {"ok": True},
            "workbook_mutated": False,
            "ended_at_epoch": 2.0,
        }
    )

    ledger.prepare_terminal(key, SUCCESS, terminal_name)
    emitted = writer.emit_record(
        RECEIPTS_FOLDER_ID, terminal_name, terminal, lease=lease, now=2.0
    )
    ledger.mark_terminal_uploaded(key, emitted["drive_id"], emitted["sha256"])
    assert ledger.state(key)["state"] == "TERMINAL_UPLOADED"

    # Restart all local state objects after the upload but before RESOLVED.
    restarted_store = DurableStateStore(state_root)
    restarted_leases = LeaseRegistry(store=restarted_store)
    restarted_ledger = ClaimLedger(store=restarted_store)
    restarted_writer = SafeDriveWriter(
        client, AppendOnlySpool(spool_root), leases=restarted_leases
    )
    restarted_runner = DurableGate0Runner(
        restarted_writer, restarted_ledger, restarted_leases
    )
    durable_lease = restarted_leases.require_valid(lease, 3.0)
    result = restarted_runner.terminalize(
        key, SUCCESS, {"ok": True}, durable_lease, now=3.0
    )

    assert result["claim"]["state"] == "RESOLVED"
    assert restarted_ledger.state(key)["state"] == "RESOLVED"
    assert len(client.find_all_by_name(RECEIPTS_FOLDER_ID, terminal_name)) == 1
    assert canonical_json_bytes(terminal) == client.download(emitted["drive_id"])
