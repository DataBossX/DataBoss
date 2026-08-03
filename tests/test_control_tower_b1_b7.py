"""Acceptance regressions for PR #82 repair findings B1 through B7."""

import pytest

from control_tower.constants import (
    MODE_MUTATION,
    QUEUE_FOLDER_ID,
    RECEIPTS_FOLDER_ID,
    TERMINALIZED_RETIRED_COMMAND_IDENTITIES,
    ClaimConflict,
    ControlTowerError,
    LeaseExpired,
)
from control_tower.drive import DriveOutage, OfflineDriveClient, SafeDriveWriter
from control_tower.durable import DurableStateStore
from control_tower.durable_runner import DurableGate0Runner
from control_tower.kernel import (
    AppendOnlySpool,
    ClaimLedger,
    LeaseRegistry,
    TaskEnvelope,
    WriterACK,
)
from control_tower.reconstruction import (
    NONCANONICAL_SECTION32_SHA256,
    CanonicalStartupReconstructor,
)
from control_tower.safety import canonical_json_bytes, sha256_hex

SUCCESS = "S32_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY"
ORIGINAL_COMMAND_ID, ORIGINAL_COMMAND_DRIVE_ID = (
    TERMINALIZED_RETIRED_COMMAND_IDENTITIES[0]
)


def command(command_id="CMD-SUCCESSOR", **extra):
    record = {
        "id": "DRIVE-" + command_id,
        "parentId": QUEUE_FOLDER_ID,
        "title": "display text only",
        "command_id": command_id,
    }
    record.update(extra)
    return record


def authority(holder="writer", scope="section32", suffix="1", expires_at=100.0):
    envelope = TaskEnvelope(
        "TE-" + suffix,
        mode=MODE_MUTATION,
        activated=True,
        body={
            "actor": holder,
            "operation": "GATE0_CONTROL_TRANSITION",
            "scope": scope,
            "input_hashes": {"command": "A" * 64},
            "control_hashes": {"rules": "B" * 64},
            "output_allowlist": [RECEIPTS_FOLDER_ID],
            "expires_at": expires_at,
        },
    )
    ack = WriterACK(
        "ACK-" + suffix,
        envelope.digest,
        holder,
        envelope.body["operation"],
        scope,
        expires_at,
    )
    return envelope, ack


def canonical_retirement_startup(client, store, suffix="BASE"):
    semantic_identity = "ORIGINAL-GATE0-PERMANENTLY-RETIRED"
    payload = canonical_json_bytes(
        {
            "schema": "databossx.retirement.v1",
            "semantic_identity": semantic_identity,
        }
    )
    file_id = "PIN-ORIGINAL-RETIREMENT-" + suffix
    name = "original-gate0-retirement-" + suffix.lower() + ".json"
    client.seed(file_id, RECEIPTS_FOLDER_ID, name, payload)
    return CanonicalStartupReconstructor(
        client,
        store,
        [
            {
                "parent_id": RECEIPTS_FOLDER_ID,
                "file_id": file_id,
                "name": name,
                "bytes": len(payload),
                "sha256": sha256_hex(payload),
                "schema": "databossx.retirement.v1",
                "semantic_identity": semantic_identity,
                "kind": "retired_command",
                "command_id": ORIGINAL_COMMAND_ID,
                "command_drive_id": ORIGINAL_COMMAND_DRIVE_ID,
            }
        ],
    )


def stack(tmp_path, client=None, startup=None):
    store = DurableStateStore(str(tmp_path / "state"))
    leases = LeaseRegistry(store=store)
    ledger = ClaimLedger(store=store)
    client = client or OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    writer = SafeDriveWriter(client, spool, leases=leases)
    if startup == "pinned":
        startup = canonical_retirement_startup(client, store)
    runner = DurableGate0Runner(
        writer, ledger, leases, startup_reconstructor=startup
    )
    return store, leases, ledger, client, spool, writer, runner


def state_bytes(store):
    with open(store.path, "rb") as handle:
        return handle.read()


def test_b1_retired_replay_has_byte_for_byte_zero_state_delta(tmp_path):
    store, _leases, ledger, client, spool, _writer, runner = stack(tmp_path)
    ledger.retire_command("RETIRED", evidence={"terminal": True})
    before = state_bytes(store)
    before_journal = spool.read_journal()
    before_drive = dict(client._files)

    with pytest.raises(ClaimConflict):
        runner.claim(command("RETIRED"), 1, "writer", now=1.0, ttl_seconds=10)

    assert state_bytes(store) == before
    assert spool.read_journal() == before_journal
    assert client._files == before_drive


def test_b1_original_retirement_survives_fresh_and_wiped_store(tmp_path):
    root = tmp_path / "state"
    store = DurableStateStore(str(root))
    ledger = ClaimLedger(store=store)
    assert store.is_retired(ORIGINAL_COMMAND_ID) is True
    before = state_bytes(store)
    key = ORIGINAL_COMMAND_ID + "|" + ORIGINAL_COMMAND_DRIVE_ID + "|4"
    with pytest.raises(ClaimConflict, match="permanently retired"):
        ledger.open(key, "attacker", now=1.0)
    assert state_bytes(store) == before

    for child in root.iterdir():
        child.unlink()
    root.rmdir()
    wiped = DurableStateStore(str(root))
    wiped_ledger = ClaimLedger(store=wiped)
    assert wiped.is_retired(ORIGINAL_COMMAND_ID) is True
    before_wiped_attempt = state_bytes(wiped)
    with pytest.raises(ClaimConflict, match="permanently retired"):
        wiped_ledger.prepare_open(key, "attacker", 2.0, "start.json")
    assert state_bytes(wiped) == before_wiped_attempt


def test_b1_original_drive_identity_cannot_be_relabelled_and_claimed(tmp_path):
    store, _leases, _ledger, client, spool, _writer, runner = stack(tmp_path)
    before = state_bytes(store)
    with pytest.raises(ClaimConflict, match="permanently retired"):
        runner.claim(
            command("RELABELLED", id=ORIGINAL_COMMAND_DRIVE_ID),
            4,
            "attacker",
            now=1.0,
            ttl_seconds=10,
        )
    assert state_bytes(store) == before
    assert client._files == {}
    assert spool.read_journal() == []


def test_b2_stale_lease_cannot_prepare_terminal_or_freeze_fields(tmp_path):
    store, leases, ledger, _client, _spool, _writer, runner = stack(tmp_path)
    claimed = runner.claim(command(), 1, "writer", now=1.0, ttl_seconds=10)
    leases.release(claimed["lease"])
    leases.acquire("section32", "successor", now=2.0, ttl_seconds=10)
    before = state_bytes(store)

    with pytest.raises(LeaseExpired):
        runner.terminalize(
            claimed["claim_key"], SUCCESS, {"ok": True}, claimed["lease"], now=3.0
        )

    assert state_bytes(store) == before
    record = ledger.state(claimed["claim_key"])
    assert record["state"] == "OPEN"
    assert "terminal_name" not in record
    assert "terminal_expected_sha256" not in record


class SupersedingCreateClient(OfflineDriveClient):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def create(self, folder_id, name, payload, mime_type):
        created = super().create(folder_id, name, payload, mime_type)
        self.callback()
        return created


def test_b3_supersession_during_network_window_creates_orphan_not_success(tmp_path):
    store = DurableStateStore(str(tmp_path / "state"))
    leases = LeaseRegistry(store=store)
    lease = leases.acquire("section32", "writer", now=1.0, ttl_seconds=100)

    def supersede():
        leases.release(lease)
        leases.acquire("section32", "successor", now=2.0, ttl_seconds=100)

    client = SupersedingCreateClient(supersede)
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    writer = SafeDriveWriter(client, spool, leases=leases)
    with pytest.raises(LeaseExpired):
        writer.emit_record(
            RECEIPTS_FOLDER_ID,
            "race.json",
            {"event": "race"},
            lease=lease,
            now=1.5,
        )
    assert len(client.find_all_by_name(RECEIPTS_FOLDER_ID, "race.json")) == 1
    assert spool.read_journal()[-1]["event"] == "ORPHAN_CREATED_AFTER_AUTHORITY_LOSS"
    assert spool.read_journal()[-1]["reconciliation_required"] is True


def test_b4_live_transition_requires_and_single_uses_exact_envelope_ack(tmp_path):
    class LiveClient(OfflineDriveClient):
        is_offline = False

    client = LiveClient()
    store, _leases, _ledger, _client, _spool, _writer, runner = stack(
        tmp_path, client=client, startup="pinned"
    )
    before = state_bytes(store)
    with pytest.raises(ControlTowerError):
        runner.claim(command(), 1, "writer", now=1.0, ttl_seconds=10)
    assert state_bytes(store) == before

    envelope, ack = authority()
    first = runner.claim(
        command(),
        1,
        "writer",
        now=1.0,
        ttl_seconds=10,
        task_envelope=envelope,
        writer_ack=ack,
    )
    assert first["claim"]["state"] == "OPEN"
    before_replay = state_bytes(store)
    with pytest.raises(ClaimConflict):
        runner.claim(
            command("CMD-OTHER"),
            1,
            "writer",
            now=2.0,
            ttl_seconds=10,
            task_envelope=envelope,
            writer_ack=ack,
        )
    assert state_bytes(store) == before_replay


@pytest.mark.parametrize("field", ["input_hashes", "control_hashes"])
def test_b4_empty_hash_bindings_fail_before_state_mutation(tmp_path, field):
    class LiveClient(OfflineDriveClient):
        is_offline = False

    client = LiveClient()
    store, _leases, _ledger, _client, _spool, _writer, runner = stack(
        tmp_path, client=client, startup="pinned"
    )
    envelope, ack = authority()
    envelope.body[field] = {}
    ack = WriterACK(
        ack.ack_id,
        envelope.digest,
        ack.actor,
        ack.operation,
        ack.scope,
        ack.expires_at,
    )
    before = state_bytes(store)
    with pytest.raises(ControlTowerError, match=field):
        runner.claim(
            command(),
            1,
            "writer",
            now=1.0,
            ttl_seconds=10,
            task_envelope=envelope,
            writer_ack=ack,
        )
    assert state_bytes(store) == before


def test_b5_live_terminal_entry_requires_startup_reconstruction(tmp_path):
    class LiveClient(OfflineDriveClient):
        is_offline = False

    client = LiveClient()
    store, leases, ledger, _client, spool, _writer, runner = stack(
        tmp_path, client=client, startup="pinned"
    )
    envelope, ack = authority()
    claimed = runner.claim(
        command(),
        1,
        "writer",
        now=1.0,
        ttl_seconds=10,
        task_envelope=envelope,
        writer_ack=ack,
    )
    runner.startup_reconstructor = None
    before = state_bytes(store)
    before_journal = spool.read_journal()
    with pytest.raises(ControlTowerError, match="startup reconstruction"):
        runner.terminalize(
            claimed["claim_key"],
            SUCCESS,
            {"ok": True},
            claimed["lease"],
            now=2.0,
            task_envelope=envelope,
            writer_ack=ack,
        )
    assert state_bytes(store) == before
    assert spool.read_journal() == before_journal
    assert ledger.state(claimed["claim_key"])["state"] == "OPEN"
    assert store.read()["leases"]["section32"]["lease_id"] == claimed[
        "lease"
    ].lease_id


def test_b5_startup_reconstruction_exact_pins_and_duplicate_fail_closed(tmp_path):
    payload = canonical_json_bytes(
        {
            "schema": "databossx.retirement.v1",
            "semantic_identity": "ORIGINAL-GATE0-PERMANENTLY-RETIRED",
        }
    )
    client = OfflineDriveClient()
    client.seed("PIN-1", RECEIPTS_FOLDER_ID, "retired.json", payload)
    store = DurableStateStore(str(tmp_path / "state"))
    pin = {
        "parent_id": RECEIPTS_FOLDER_ID,
        "file_id": "PIN-1",
        "name": "retired.json",
        "bytes": len(payload),
        "sha256": sha256_hex(payload),
        "schema": "databossx.retirement.v1",
        "semantic_identity": "ORIGINAL-GATE0-PERMANENTLY-RETIRED",
        "kind": "retired_command",
        "command_id": ORIGINAL_COMMAND_ID,
        "command_drive_id": ORIGINAL_COMMAND_DRIVE_ID,
    }
    result = CanonicalStartupReconstructor(client, store, [pin]).ensure_reconstructed()
    assert result["verified"] == 1
    assert store.is_retired(ORIGINAL_COMMAND_ID) is True

    other = DurableStateStore(str(tmp_path / "other"))
    client.seed("PIN-2", RECEIPTS_FOLDER_ID, "retired.json", payload)
    before = state_bytes(other)
    with pytest.raises(ControlTowerError):
        CanonicalStartupReconstructor(client, other, [pin]).ensure_reconstructed()
    assert state_bytes(other) == before


def test_b5_empty_reconstruction_pin_set_fails_without_state_mutation(tmp_path):
    client = OfflineDriveClient()
    store = DurableStateStore(str(tmp_path / "state"))
    before = state_bytes(store)
    with pytest.raises(ControlTowerError, match="non-empty exact pins"):
        CanonicalStartupReconstructor(client, store, []).ensure_reconstructed()
    assert state_bytes(store) == before


def test_b1_live_retired_replay_after_reconstruction_has_zero_state_delta(tmp_path):
    class LiveClient(OfflineDriveClient):
        is_offline = False

    payload = canonical_json_bytes(
        {
            "schema": "databossx.retirement.v1",
            "semantic_identity": "ORIGINAL-GATE0-PERMANENTLY-RETIRED",
        }
    )
    client = LiveClient()
    client.seed("PIN-LIVE", RECEIPTS_FOLDER_ID, "retired-live.json", payload)
    store = DurableStateStore(str(tmp_path / "state"))
    pin = {
        "parent_id": RECEIPTS_FOLDER_ID,
        "file_id": "PIN-LIVE",
        "name": "retired-live.json",
        "bytes": len(payload),
        "sha256": sha256_hex(payload),
        "schema": "databossx.retirement.v1",
        "semantic_identity": "ORIGINAL-GATE0-PERMANENTLY-RETIRED",
        "kind": "retired_command",
        "command_id": ORIGINAL_COMMAND_ID,
        "command_drive_id": ORIGINAL_COMMAND_DRIVE_ID,
    }
    CanonicalStartupReconstructor(client, store, [pin]).ensure_reconstructed()
    leases = LeaseRegistry(store=store)
    ledger = ClaimLedger(store=store)
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    runner = DurableGate0Runner(
        SafeDriveWriter(client, spool, leases=leases),
        ledger,
        leases,
        startup_reconstructor=CanonicalStartupReconstructor(client, store, [pin]),
    )
    envelope, ack = authority(suffix="live")
    before = state_bytes(store)
    before_drive = dict(client._files)
    with pytest.raises(ClaimConflict, match="retired"):
        runner.claim(
            command(ORIGINAL_COMMAND_ID, id=ORIGINAL_COMMAND_DRIVE_ID),
            1,
            "writer",
            now=1.0,
            ttl_seconds=10,
            task_envelope=envelope,
            writer_ack=ack,
        )
    assert state_bytes(store) == before
    assert spool.read_journal() == []
    assert client._files == before_drive


def test_b6_expired_start_recovers_once_under_new_fence_without_new_start_bytes(tmp_path):
    store, _leases, ledger, client, spool, _writer, runner = stack(tmp_path)
    client.outage = True
    with pytest.raises(DriveOutage):
        runner.claim(command(), 1, "writer", now=1.0, ttl_seconds=1)
    key = "CMD-SUCCESSOR|DRIVE-CMD-SUCCESSOR|1"
    frozen = canonical_json_bytes(ledger.state(key)["start_receipt_payload"])
    first_fence = ledger.state(key)["start_receipt_payload"]["fencing_sequence"]

    client.outage = False
    recovered = runner.recover_start(
        command(), 1, "writer", now=3.0, ttl_seconds=10
    )
    assert recovered["lease"].fencing_sequence == first_fence + 1
    assert client.download(recovered["receipt"]["drive_id"]) == frozen
    assert len(
        client.find_all_by_name(
            RECEIPTS_FOLDER_ID, ledger.state(key)["start_receipt_name"]
        )
    ) == 1
    assert spool.read_record(ledger.state(key)["start_receipt_name"]) == frozen


def test_b7_exact_noncanonical_fixture_has_zero_authority_state_delta(tmp_path):
    store, _leases, _ledger, client, spool, _writer, runner = stack(tmp_path)
    before = state_bytes(store)
    with pytest.raises(ControlTowerError, match="noncanonical"):
        runner.claim(
            command(candidate_sha256=NONCANONICAL_SECTION32_SHA256),
            1,
            "writer",
            now=1.0,
            ttl_seconds=10,
        )
    assert state_bytes(store) == before
    assert client._files == {}
    assert spool.read_journal() == []
