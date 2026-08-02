"""Tests for the DataBossX Control Tower control kernel.

Each test names the control property it defends. A guard is only useful if it
refuses, so most of these assert that an exception is raised -- a test that
merely calls the happy path would pass against a kernel with every check
deleted.
"""

import os

import pytest

from control_tower.audit import MISMATCH, OBSERVED, UNREACHABLE, audit_expected_file, run_audit
from control_tower.constants import (
    ALLOWED_WRITE_FOLDER_IDS,
    HOLD,
    MODE_MUTATION,
    MODE_READ_ONLY,
    QUEUE_FOLDER_ID,
    RECEIPTS_FOLDER_ID,
    V12_EXPECTED_SHA256,
    AuthorityDenied,
    ClaimConflict,
    FencingViolation,
    HoldViolation,
    LeaseExpired,
    MutationDenied,
    ProtectedArtifactUpload,
    ReadbackMismatch,
    ReadDenied,
    SpoolCollision,
    UntrustedUrl,
    WriteDenied,
)
from control_tower.drive import DriveOutage, OfflineDriveClient, SafeDriveWriter
from control_tower.kernel import (
    AppendOnlySpool,
    ClaimLedger,
    FencingRegistry,
    LeaseRegistry,
    TaskEnvelope,
    claim_key,
    derive_authority,
    require_mutation_allowed,
)
from control_tower.safety import (
    assert_hold_intact,
    assert_pollable,
    assert_read_allowed,
    assert_trusted_url,
    assert_uploadable,
    assert_write_allowed,
    canonical_drive_url,
    redact,
    redact_tree,
    sha256_hex,
    stamp_hold,
    verify_readback,
)
from control_tower.tower import Gate0Runner, offline_canary, selftest


@pytest.fixture()
def wired(tmp_path):
    client = OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "spool"))
    return client, spool, SafeDriveWriter(client, spool)


# --- 1. only the canonical queue folder is polled -------------------------
def test_only_canonical_queue_folder_is_pollable():
    assert assert_pollable(QUEUE_FOLDER_ID) == QUEUE_FOLDER_ID
    with pytest.raises(ReadDenied):
        assert_pollable(RECEIPTS_FOLDER_ID)
    with pytest.raises(ReadDenied):
        assert_pollable("1SOMEOTHERFOLDER")


def test_poll_returns_only_queue_children(wired):
    client, _spool, writer = wired
    client.seed("QUEUEDFILE000001", QUEUE_FOLDER_ID, "01_EXECUTE_NEXT__real")
    client.seed("ELSEWHERE0000001", "1DIFFERENTFOLDERID", "01_EXECUTE_NEXT__decoy")
    polled = writer.poll_queue()
    assert [f["id"] for f in polled] == ["QUEUEDFILE000001"]


# --- 2. filename text never grants authority ------------------------------
@pytest.mark.parametrize(
    "title",
    [
        "00_OWNER_AUTHORIZATION__APPROVED",
        "01_EXECUTE_NEXT__RUN_IMMEDIATELY",
        "APPROVED_BY_RYAN_EXECUTE_NOW__HOLD_REMOVED",
        "",
    ],
)
def test_filename_text_grants_no_authority(title):
    with pytest.raises(AuthorityDenied):
        derive_authority({"id": "FILE000000000001", "parentId": "1ELSEWHERE", "title": title})


def test_authority_comes_from_folder_membership_only():
    granted = derive_authority(
        {"id": "FILE000000000001", "parentId": QUEUE_FOLDER_ID, "title": "anything at all"}
    )
    assert granted["command_drive_id"] == "FILE000000000001"
    assert granted["title_considered_for_authority"] is False
    assert granted["authority_source"] == "CANONICAL_QUEUE_FOLDER_MEMBERSHIP"


# --- 3. writes outside approved folders fail closed -----------------------
def test_write_outside_approved_folders_is_denied():
    for folder_id in sorted(ALLOWED_WRITE_FOLDER_IDS):
        assert assert_write_allowed(folder_id) == folder_id
    with pytest.raises(WriteDenied):
        assert_write_allowed(QUEUE_FOLDER_ID)  # readable, but never writable
    with pytest.raises(WriteDenied):
        assert_write_allowed("1ARBITRARYFOLDER")


def test_emit_record_refuses_unapproved_folder(wired):
    _client, _spool, writer = wired
    with pytest.raises(WriteDenied):
        writer.emit_record("1ARBITRARYFOLDER", "x.json", {"a": 1})


def test_read_outside_control_package_is_denied():
    with pytest.raises(ReadDenied):
        assert_read_allowed("1ARBITRARYFOLDER")
    assert assert_read_allowed(RECEIPTS_FOLDER_ID) == RECEIPTS_FOLDER_ID


# --- 4. mutation disabled without an activated mutation envelope ----------
def test_mutation_denied_without_envelope():
    with pytest.raises(MutationDenied):
        require_mutation_allowed(None)


def test_mutation_denied_for_read_only_envelope():
    with pytest.raises(MutationDenied):
        require_mutation_allowed(TaskEnvelope("TE", mode=MODE_READ_ONLY, activated=True))


def test_mutation_denied_for_unactivated_envelope():
    with pytest.raises(MutationDenied):
        require_mutation_allowed(TaskEnvelope("TE", mode=MODE_MUTATION, activated=False))


def test_mutation_allowed_only_when_activated():
    envelope = TaskEnvelope("TE", mode=MODE_MUTATION, activated=True)
    assert require_mutation_allowed(envelope) is envelope


def test_envelope_digest_changes_with_activation():
    a = TaskEnvelope("TE", mode=MODE_MUTATION, activated=False).digest
    b = TaskEnvelope("TE", mode=MODE_MUTATION, activated=True).digest
    assert a != b


# --- 5. the exactly-once key matches the controlling contract -------------
def test_claim_key_binds_command_drive_id_and_revision():
    assert claim_key("CMD", "DRIVE", 4) == "CMD|DRIVE|4"
    assert claim_key("CMD", "DRIVE", 4) != claim_key("CMD", "DRIVE", 5)
    assert claim_key("CMD", "DRIVE", 4) != claim_key("CMD2", "DRIVE", 4)


@pytest.mark.parametrize("missing", [(None, "D", 1), ("C", None, 1), ("C", "D", None), ("", "D", 1)])
def test_claim_key_requires_every_component(missing):
    with pytest.raises(AuthorityDenied):
        claim_key(*missing)


# --- 6. an unresolved claim prevents a second claim -----------------------
def test_unresolved_claim_blocks_a_second_claim():
    ledger = ClaimLedger()
    ledger.open("K", "writer-A", now=0.0)
    with pytest.raises(ClaimConflict):
        ledger.open("K", "writer-B", now=1.0)


def test_resolved_claim_cannot_be_reclaimed():
    ledger = ClaimLedger()
    ledger.open("K", "writer-A", now=0.0)
    ledger.resolve("K", "S32_AUTHORITY_REISSUE_COMPILATION_BLOCKED")
    with pytest.raises(ClaimConflict):
        ledger.open("K", "writer-A", now=2.0)


def test_resolving_unknown_claim_is_refused():
    with pytest.raises(ClaimConflict):
        ClaimLedger().resolve("NOPE", "S32_AUTHORITY_REISSUE_COMPILATION_BLOCKED")


# --- 7. a stale lease cannot write ----------------------------------------
def test_expired_lease_cannot_write():
    leases = LeaseRegistry()
    lease = leases.acquire("scope", "A", now=0.0, ttl_seconds=10)
    assert leases.require_valid(lease, 5.0) is lease
    with pytest.raises(LeaseExpired):
        leases.require_valid(lease, 11.0)


def test_released_lease_cannot_write():
    leases = LeaseRegistry()
    lease = leases.acquire("scope", "A", now=0.0, ttl_seconds=100)
    leases.release(lease)
    with pytest.raises(LeaseExpired):
        leases.require_valid(lease, 1.0)


def test_second_holder_cannot_take_an_active_lease():
    leases = LeaseRegistry()
    leases.acquire("scope", "A", now=0.0, ttl_seconds=100)
    with pytest.raises(ClaimConflict):
        leases.acquire("scope", "B", now=1.0, ttl_seconds=100)


def test_lease_is_reacquirable_after_expiry():
    leases = LeaseRegistry()
    first = leases.acquire("scope", "A", now=0.0, ttl_seconds=10)
    second = leases.acquire("scope", "B", now=50.0, ttl_seconds=10)
    assert second.fencing_sequence > first.fencing_sequence


def test_emit_record_requires_a_valid_lease(tmp_path):
    client = OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "s"))
    leases = LeaseRegistry()
    writer = SafeDriveWriter(client, spool, leases=leases)
    lease = leases.acquire("scope", "A", now=0.0, ttl_seconds=10)
    with pytest.raises(LeaseExpired):
        writer.emit_record(RECEIPTS_FOLDER_ID, "r.json", {"a": 1}, lease=lease, now=999.0)


# --- 8. monotonic fencing is enforced -------------------------------------
def test_fencing_sequence_is_monotonic():
    fencing = FencingRegistry()
    assert fencing.next_sequence("s") == 1
    assert fencing.next_sequence("s") == 2
    assert fencing.highest("s") == 2


def test_stale_fencing_token_is_rejected():
    fencing = FencingRegistry()
    fencing.next_sequence("s")
    fencing.next_sequence("s")
    with pytest.raises(FencingViolation):
        fencing.require_strictly_current("s", 1)


def test_zombie_writer_with_old_token_cannot_write():
    leases = LeaseRegistry()
    old = leases.acquire("scope", "A", now=0.0, ttl_seconds=1000)
    leases.release(old)
    leases.acquire("scope", "B", now=1.0, ttl_seconds=1000)
    # The zombie's lease has not expired by wall clock, but its token is stale.
    with pytest.raises(FencingViolation):
        leases.fencing.require_strictly_current("scope", old.fencing_sequence)


def test_non_integer_fencing_sequence_is_rejected():
    with pytest.raises(FencingViolation):
        FencingRegistry().require("s", "1")


# --- 9. the spool is append-only and collision-safe -----------------------
def test_spool_refuses_to_overwrite(tmp_path):
    spool = AppendOnlySpool(str(tmp_path / "s"))
    spool.put_record("a.json", b"original")
    with pytest.raises(SpoolCollision):
        spool.put_record("a.json", b"replacement")
    with open(os.path.join(spool.root, "a.json"), "rb") as handle:
        assert handle.read() == b"original"


def test_spool_journal_appends(tmp_path):
    spool = AppendOnlySpool(str(tmp_path / "s"))
    spool.append({"event": "one"})
    spool.append({"event": "two"})
    entries = spool.read_journal()
    assert [e["event"] for e in entries] == ["one", "two"]
    assert all(e["hold"] == HOLD for e in entries)


def test_spool_records_digest_and_size(tmp_path):
    spool = AppendOnlySpool(str(tmp_path / "s"))
    info = spool.put_record("a.json", b"abc")
    assert info["bytes"] == 3
    assert info["sha256"] == sha256_hex(b"abc")


# --- 10. Drive outages do not drop or overwrite receipts ------------------
def test_outage_retains_spooled_evidence_and_marks_pending(tmp_path):
    client = OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "s"))
    writer = SafeDriveWriter(client, spool)
    client.outage = True
    with pytest.raises(DriveOutage):
        writer.emit_record(RECEIPTS_FOLDER_ID, "r.json", {"a": 1})
    assert os.path.exists(os.path.join(spool.root, "r.json"))
    assert any(e["event"] == "UPLOAD_PENDING_DRIVE_OUTAGE" for e in spool.read_journal())


def test_retry_after_outage_does_not_overwrite(tmp_path):
    client = OfflineDriveClient()
    spool = AppendOnlySpool(str(tmp_path / "s"))
    writer = SafeDriveWriter(client, spool)
    client.outage = True
    with pytest.raises(DriveOutage):
        writer.emit_record(RECEIPTS_FOLDER_ID, "r.json", {"a": 1})
    client.outage = False
    with pytest.raises(SpoolCollision):
        writer.emit_record(RECEIPTS_FOLDER_ID, "r.json", {"a": 1})


def test_drive_create_refuses_duplicate_name(wired):
    client, _spool, writer = wired
    writer.emit_record(RECEIPTS_FOLDER_ID, "once.json", {"a": 1})
    assert client.find_by_name(RECEIPTS_FOLDER_ID, "once.json") is not None


def test_readback_mismatch_is_detected(tmp_path):
    client = OfflineDriveClient()
    client.corrupt_readback = True
    spool = AppendOnlySpool(str(tmp_path / "s"))
    writer = SafeDriveWriter(client, spool)
    with pytest.raises(ReadbackMismatch):
        writer.emit_record(RECEIPTS_FOLDER_ID, "r.json", {"a": 1})


def test_verify_readback_catches_length_and_content():
    with pytest.raises(ReadbackMismatch):
        verify_readback(b"abc", b"abcd")
    with pytest.raises(ReadbackMismatch):
        verify_readback(b"abc", b"abd")
    assert verify_readback(b"abc", b"abc") == sha256_hex(b"abc")


# --- 11. secret values are redacted ---------------------------------------
@pytest.mark.parametrize(
    "secret",
    [
        "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
        "ya29.a0AfH6SMBexampletokenvalue",
        "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    ],
)
def test_secret_values_are_redacted(secret):
    assert secret not in redact("credential is {0} end".format(secret))


def test_keyed_secrets_are_redacted_but_keys_remain():
    scrubbed = redact('password: "hunter2secret" and api_key=abcdef123456')
    assert "hunter2secret" not in scrubbed
    assert "abcdef123456" not in scrubbed
    assert "password" in scrubbed and "api_key" in scrubbed


def test_redaction_walks_nested_structures():
    tree = {"a": ["token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"], "b": {"c": "safe"}}
    out = redact_tree(tree)
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" not in str(out)
    assert out["b"]["c"] == "safe"


def test_emitted_records_are_redacted(wired):
    _client, spool, writer = wired
    writer.emit_record(
        RECEIPTS_FOLDER_ID, "r.json", {"note": "token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"}
    )
    with open(os.path.join(spool.root, "r.json"), "rb") as handle:
        assert b"ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" not in handle.read()


# --- 12. source evidence and protected workbooks cannot be uploaded -------
def test_protected_workbook_digest_is_refused(monkeypatch):
    """A payload is refused by digest even when its name looks innocuous.

    The pinned baselines are real workbook digests we cannot reproduce here, so
    the pin set is swapped for the digest of a payload we control. That still
    exercises the branch that matters: the guard consults content, not naming.
    """
    payload = b'{"looks":"like a harmless control record"}'
    monkeypatch.setattr(
        "control_tower.safety.PROTECTED_WORKBOOK_SHA256", frozenset({sha256_hex(payload)})
    )
    with pytest.raises(ProtectedArtifactUpload):
        assert_uploadable(payload, "receipt.json", "application/json")


def test_v12_baseline_is_pinned_as_protected():
    from control_tower.constants import PROTECTED_WORKBOOK_SHA256

    assert V12_EXPECTED_SHA256 in PROTECTED_WORKBOOK_SHA256


def test_office_container_signature_is_refused():
    with pytest.raises(ProtectedArtifactUpload):
        assert_uploadable(b"PK\x03\x04 rest of a zip", "innocent.json", "application/json")


@pytest.mark.parametrize("name", ["a.xlsx", "a.pdf", "a.zip", "scan.tiff", "sheet.csv"])
def test_prohibited_suffixes_are_refused(name):
    with pytest.raises(ProtectedArtifactUpload):
        assert_uploadable(b"{}", name, "application/json")


@pytest.mark.parametrize("mime", ["application/pdf", "image/png", "application/vnd.ms-excel"])
def test_prohibited_mime_types_are_refused(mime):
    with pytest.raises(ProtectedArtifactUpload):
        assert_uploadable(b"{}", "a.json", mime)


def test_plain_control_record_is_uploadable():
    assert assert_uploadable(b'{"ok":true}', "receipt.json", "application/json")


# --- 13. the HOLD cannot be removed or altered ----------------------------
def test_hold_is_stamped_on_every_record():
    assert stamp_hold({"a": 1})["hold"] == HOLD


def test_altering_the_hold_is_refused():
    with pytest.raises(HoldViolation):
        stamp_hold({"hold": "RELEASED FOR EXTERNAL DELIVERY"})
    with pytest.raises(HoldViolation):
        stamp_hold({"hold": ""})


def test_missing_hold_is_detected():
    with pytest.raises(HoldViolation):
        assert_hold_intact({"a": 1})
    assert assert_hold_intact({"hold": HOLD})


def test_emitted_record_carries_the_hold(wired):
    client, _spool, writer = wired
    emitted = writer.emit_record(RECEIPTS_FOLDER_ID, "r.json", {"a": 1})
    payload = client.download(emitted["drive_id"]).decode("utf-8")
    assert HOLD in payload


# --- 14. canonical Drive URLs from verified IDs only ----------------------
def test_canonical_url_built_from_id():
    url = canonical_drive_url("1C0C8ERuCYm6Rqso0ahLXMifhXqlYjinOlFkN5k29NCE")
    assert url == (
        "https://drive.google.com/file/d/1C0C8ERuCYm6Rqso0ahLXMifhXqlYjinOlFkN5k29NCE/view"
    )


@pytest.mark.parametrize("bad", ["../../etc", "id with spaces", "", "short", "a/b", None])
def test_malformed_ids_are_refused(bad):
    with pytest.raises(UntrustedUrl):
        canonical_drive_url(bad)


# --- 15. no non-Google URL is followed or trusted -------------------------
@pytest.mark.parametrize(
    "url",
    [
        "https://docichat.com/open?state=abc",
        "https://www.docichat.com/open",
        "https://livepolls.app/x",
        "https://evil.example.com/drive",
        "http://drive.google.com/file/d/ABCDEFGHIJ/view",
    ],
)
def test_untrusted_urls_are_refused(url):
    with pytest.raises(UntrustedUrl):
        assert_trusted_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://drive.google.com/file/d/ABCDEFGHIJ/view",
        "https://docs.google.com/document/d/ABCDEFGHIJ/edit",
    ],
)
def test_trusted_google_urls_are_accepted(url):
    assert assert_trusted_url(url) == url


# --- audit behaviour ------------------------------------------------------
def test_audit_marks_absent_target_unreachable_not_pass():
    result = audit_expected_file("/definitely/not/here.xlsx", V12_EXPECTED_SHA256)
    assert result["status"] == UNREACHABLE


def test_audit_detects_hash_mismatch(tmp_path):
    target = tmp_path / "wb.xlsx"
    target.write_bytes(b"not the real workbook")
    result = audit_expected_file(str(target), V12_EXPECTED_SHA256)
    assert result["status"] == MISMATCH
    assert result["sha256"] != V12_EXPECTED_SHA256


def test_audit_confirms_exact_match(tmp_path):
    target = tmp_path / "wb.bin"
    target.write_bytes(b"payload")
    result = audit_expected_file(str(target), sha256_hex(b"payload"))
    assert result["status"] == OBSERVED


def test_audit_never_reports_complete_when_target_unreachable(tmp_path):
    report = run_audit(client=None, v12_path=None, repo_path=str(tmp_path))
    assert report["audit_completeness"] == "PARTIAL_HOST_MISMATCH"
    assert report["v12_ruling"] == "NOT_VERIFIED_UNREACHABLE"
    assert report["workbook_opened"] is False
    assert report["workbook_mutated"] is False


def test_audit_reads_drive_surface(wired):
    client, _spool, _writer = wired
    client.seed("Q1", QUEUE_FOLDER_ID, "cmd")
    report = run_audit(client=client, repo_path=None)
    assert report["drive_surface"]["queue"]["child_count"] == 1


# --- selftest and canary --------------------------------------------------
def test_selftest_passes_completely():
    report = selftest()
    failures = [c["name"] for c in report["checks"] if not c["passed"]]
    assert failures == [], "failing checks: {0}".format(failures)
    assert report["ok"] is True
    assert report["drive_writes"] == 0


def test_offline_canary_passes_completely():
    report = offline_canary()
    assert report["ok"] is True
    assert report["network_calls"] == 0
    assert report["total"] == 7


def test_gate0_preflight_requires_passing_selftest(wired):
    _client, _spool, writer = wired
    assert Gate0Runner(writer).preflight()["ok"] is True


# --- end to end -----------------------------------------------------------
def test_gate0_claim_and_terminalize_round_trip(wired):
    client, _spool, writer = wired
    client.seed("CMDID00000000001", QUEUE_FOLDER_ID, "01_EXECUTE_NEXT__cmd")
    runner = Gate0Runner(writer)
    meta = client.get_metadata("CMDID00000000001")
    meta["command_id"] = "DBX-S32-TEST"

    claimed = runner.claim(meta, command_revision=4, holder="tower-A", now=1000.0)
    assert claimed["receipt"]["byte_exact_match"] is True

    # A second claim of the same command+revision must lose.
    with pytest.raises(ClaimConflict):
        runner.claim(meta, command_revision=4, holder="tower-B", now=1001.0)

    audit = runner.execute_read_only(v12_path=None, repo_path=None)
    assert audit["workbook_mutated"] is False

    done = runner.terminalize(
        claimed["claim_key"],
        "S32_AUTHORITY_REISSUE_COMPILATION_BLOCKED",
        findings={"audit_completeness": audit["audit_completeness"]},
        lease=claimed["lease"],
        now=1002.0,
    )
    assert done["receipt"]["byte_exact_match"] is True
    assert done["claim"]["state"] == "RESOLVED"


def test_terminal_sentinel_must_be_one_of_the_three(wired):
    _client, _spool, writer = wired
    runner = Gate0Runner(writer)
    runner.ledger.open("K", "A", now=0.0)
    with pytest.raises(Exception):
        runner.terminalize("K", "SOME_MADE_UP_SENTINEL", findings={})


def test_gate0_run_makes_no_workbook_mutation(wired):
    _client, _spool, writer = wired
    report = Gate0Runner(writer).execute_read_only(v12_path=None, repo_path=None)
    assert report["audit_mode"] == "READ_ONLY"
    assert report["workbook_opened"] is False
