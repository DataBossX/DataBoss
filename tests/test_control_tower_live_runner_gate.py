"""The legacy in-memory runner must never become a live authority path."""

import pytest

from control_tower.constants import QUEUE_FOLDER_ID, LeaseExpired
from control_tower.drive import OfflineDriveClient, SafeDriveWriter
from control_tower.durable import DurableStateStore
from control_tower.durable_runner import DurableGate0Runner
from control_tower.kernel import AppendOnlySpool, ClaimLedger, LeaseRegistry
from control_tower.tower import Gate0Runner


class LiveClient(OfflineDriveClient):
    is_offline = False


def command():
    return {
        "id": "LIVE-CMD",
        "parentId": QUEUE_FOLDER_ID,
        "title": "display only",
        "command_id": "CMD-SUCCESSOR",
    }


def test_legacy_runner_cannot_use_live_writer_even_with_durable_lease(tmp_path):
    client = LiveClient()
    store = DurableStateStore(str(tmp_path / "state"))
    leases = LeaseRegistry(store=store)
    writer = SafeDriveWriter(
        client, AppendOnlySpool(str(tmp_path / "spool")), leases=leases
    )
    legacy = Gate0Runner(writer, leases=leases)
    with pytest.raises(LeaseExpired):
        legacy.claim(command(), 1, "writer", now=1.0, ttl_seconds=100)


def test_durable_runner_is_the_only_binding_that_enables_live_writer(tmp_path):
    client = LiveClient()
    store = DurableStateStore(str(tmp_path / "state"))
    leases = LeaseRegistry(store=store)
    ledger = ClaimLedger(store=store)
    writer = SafeDriveWriter(
        client, AppendOnlySpool(str(tmp_path / "spool")), leases=leases
    )
    DurableGate0Runner(writer, ledger, leases)
    assert writer.durable_runner_bound is True
