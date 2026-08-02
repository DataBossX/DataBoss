"""Deterministic concurrency tests for durable exactly-once controls."""

import threading

from control_tower.constants import RECEIPTS_FOLDER_ID, ClaimConflict, ControlTowerError
from control_tower.drive import OfflineDriveClient, SafeDriveWriter
from control_tower.durable import DurableStateStore
from control_tower.kernel import AppendOnlySpool, ClaimLedger, LeaseRegistry


def run_concurrently(functions):
    barrier = threading.Barrier(len(functions))
    results = []
    lock = threading.Lock()

    def wrapped(index, function):
        barrier.wait()
        try:
            value = function()
            outcome = (index, "ok", value)
        except Exception as exc:  # noqa: BLE001 - assertions inspect exact type
            outcome = (index, "error", exc)
        with lock:
            results.append(outcome)

    threads = [
        threading.Thread(target=wrapped, args=(index, function))
        for index, function in enumerate(functions)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    return sorted(results)


def test_two_concurrent_claimers_have_exactly_one_winner(tmp_path):
    root = str(tmp_path / "state")

    def claim(holder):
        ledger = ClaimLedger(store=DurableStateStore(root))
        return ledger.open("CMD|DRIVE|1", holder, now=1.0)

    results = run_concurrently(
        [lambda: claim("writer-A"), lambda: claim("writer-B")]
    )
    successes = [item for item in results if item[1] == "ok"]
    failures = [item for item in results if item[1] == "error"]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0][2], ClaimConflict)


def test_two_concurrent_lease_holders_have_exactly_one_winner(tmp_path):
    root = str(tmp_path / "state")

    def acquire(holder):
        registry = LeaseRegistry(store=DurableStateStore(root))
        return registry.acquire("section32", holder, now=1.0, ttl_seconds=100)

    results = run_concurrently(
        [lambda: acquire("writer-A"), lambda: acquire("writer-B")]
    )
    successes = [item for item in results if item[1] == "ok"]
    failures = [item for item in results if item[1] == "error"]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0][2], ClaimConflict)


class ForcedCreateRaceClient(OfflineDriveClient):
    """Force both creates to finish before either writer reconciles."""

    is_offline = False

    def __init__(self):
        super().__init__()
        self.pre_create_barrier = threading.Barrier(2)
        self.post_create_barrier = threading.Barrier(2)
        self.create_lock = threading.Lock()

    def create(self, folder_id, name, payload, mime_type):
        self._check_outage()
        self.pre_create_barrier.wait()
        with self.create_lock:
            self._seq += 1
            file_id = "RACE{0:016d}".format(self._seq)
            created = self.seed(file_id, folder_id, name, payload, mime_type)
        self.post_create_barrier.wait()
        return created


def test_two_concurrent_same_name_creators_fail_closed_on_duplicate(tmp_path):
    store = DurableStateStore(str(tmp_path / "state"))
    leases = LeaseRegistry(store=store)
    lease = leases.acquire("section32", "writer", now=1.0, ttl_seconds=100)
    client = ForcedCreateRaceClient()

    writers = []
    for index in range(2):
        writer = SafeDriveWriter(
            client,
            AppendOnlySpool(str(tmp_path / ("spool-{0}".format(index)))),
            leases=leases,
        )
        writer.bind_durable_runner(store)
        writers.append(writer)

    results = run_concurrently(
        [
            lambda: writers[0].emit_record(
                RECEIPTS_FOLDER_ID,
                "race.json",
                {"event": "same"},
                lease=lease,
                now=2.0,
            ),
            lambda: writers[1].emit_record(
                RECEIPTS_FOLDER_ID,
                "race.json",
                {"event": "same"},
                lease=lease,
                now=2.0,
            ),
        ]
    )
    assert all(item[1] == "error" for item in results)
    assert all(isinstance(item[2], ControlTowerError) for item in results)
    assert len(client.find_all_by_name(RECEIPTS_FOLDER_ID, "race.json")) == 2
