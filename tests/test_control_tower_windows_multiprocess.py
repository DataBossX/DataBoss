"""Windows process-boundary proofs for durable writer locking and fencing."""

import multiprocessing
import os

import pytest

from control_tower.durable import DurableStateStore
from control_tower.kernel import LeaseRegistry


def _crash_while_holding_lock(root, ready):
    store = DurableStateStore(root)
    with store._locked():
        ready.set()
        os._exit(73)


def _compete_for_lease(root, holder, ready, start, outcomes):
    registry = LeaseRegistry(store=DurableStateStore(root))
    ready.set()
    start.wait(10)
    try:
        lease = registry.acquire("section32", holder, now=1.0, ttl_seconds=100)
        outcomes.put((holder, "ok", lease.fencing_sequence))
    except Exception as exc:  # noqa: BLE001 - parent asserts the failure class name
        outcomes.put((holder, "error", type(exc).__name__))


@pytest.mark.skipif(os.name != "nt", reason="Windows msvcrt proof")
def test_msvcrt_lock_is_released_when_writer_process_crashes(tmp_path):
    context = multiprocessing.get_context("spawn")
    root = str(tmp_path / "state")
    DurableStateStore(root)
    ready = context.Event()
    process = context.Process(target=_crash_while_holding_lock, args=(root, ready))
    process.start()
    assert ready.wait(10)
    process.join(10)
    assert process.exitcode == 73

    store = DurableStateStore(root, lock_timeout=2.0)
    before = store.read()["revision"]
    store.transaction(lambda state: state["fencing"].update({"proof": 1}))
    after = store.read()
    assert after["revision"] == before + 1
    assert after["fencing"]["proof"] == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows msvcrt proof")
def test_windows_process_lease_race_has_one_winner_and_one_current_fence(tmp_path):
    context = multiprocessing.get_context("spawn")
    root = str(tmp_path / "state")
    DurableStateStore(root)
    ready_a = context.Event()
    ready_b = context.Event()
    start = context.Event()
    outcomes = context.Queue()
    processes = [
        context.Process(
            target=_compete_for_lease,
            args=(root, holder, ready, start, outcomes),
        )
        for holder, ready in (("writer-A", ready_a), ("writer-B", ready_b))
    ]
    for process in processes:
        process.start()
    assert ready_a.wait(10) and ready_b.wait(10)
    start.set()
    for process in processes:
        process.join(10)
        assert process.exitcode == 0

    results = sorted(outcomes.get(timeout=5) for _ in range(2))
    assert [result[1] for result in results].count("ok") == 1
    assert [result[1] for result in results].count("error") == 1
    assert [result[2] for result in results if result[1] == "error"] == [
        "ClaimConflict"
    ]
    state = DurableStateStore(root).read()
    assert state["fencing"]["section32"] == 1
    assert state["leases"]["section32"]["fencing_sequence"] == 1
