"""Orchestration: selftest, offline canary, and the Gate 0 run.

The selftest proves the kernel's invariants against an in-memory Drive before
the tower is ever pointed at the real control package. It performs no network
call and mutates nothing, so it is safe to run at any time -- and a failure
must stop execution rather than downgrade it to a warning.
"""

import getpass
import os
import platform
import socket
import sys
import time

from .audit import run_audit
from .constants import (
    ALLOWED_WRITE_FOLDER_IDS,
    GATE0_TERMINAL_SENTINELS,
    HOLD,
    MODE_MUTATION,
    MODE_READ_ONLY,
    QUEUE_FOLDER_ID,
    RECEIPTS_FOLDER_ID,
    RETIRED_GATE0_COMMAND_DRIVE_ID,
    RETIRED_GATE0_COMMAND_ID,
    SPENT_COMMAND_DRIVE_IDS,
    SPENT_COMMAND_IDS,
    STATUS_FOLDER_ID,
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
from .drive import DriveOutage, OfflineDriveClient, SafeDriveWriter
from .kernel import (
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
from .safety import (
    assert_active_command,
    assert_hold_intact,
    assert_output_allowed,
    assert_read_allowed,
    assert_trusted_url,
    assert_uploadable,
    assert_write_allowed,
    canonical_drive_url,
    canonical_json_bytes,
    make_sha256_sidecar,
    redact,
    sha256_hex,
    stamp_hold,
)


def _expect_raise(exc_type, fn, *args, **kwargs):
    """A check passes only when the guard actually refuses."""
    try:
        fn(*args, **kwargs)
    except exc_type:
        return True, "refused as required"
    except Exception as exc:  # noqa: BLE001
        return False, "wrong error type: {0}: {1}".format(type(exc).__name__, exc)
    return False, "guard did NOT refuse"


def _check(results, name, passed, detail):
    results.append({"name": name, "passed": bool(passed), "detail": detail})
    return passed


def selftest(tmp_root=None):
    """Exercise every control invariant offline. Returns a structured result."""
    import tempfile

    root = tmp_root or tempfile.mkdtemp(prefix="dbx_selftest_")
    results = []

    # 1. Only the canonical queue folder is polled.
    client = OfflineDriveClient()
    spool = AppendOnlySpool(os.path.join(root, "spool1"))
    writer = SafeDriveWriter(client, spool)
    client.seed("CMDFILE0000000001", QUEUE_FOLDER_ID, "01_EXECUTE_NEXT__thing")
    client.seed("DECOY000000000001", "1SOMEOTHERFOLDERIDNOTPINNED", "01_EXECUTE_NEXT__decoy")
    polled = writer.poll_queue()
    _check(
        results,
        "only_canonical_queue_polled",
        len(polled) == 1 and polled[0]["id"] == "CMDFILE0000000001",
        "polled {0} file(s) from the pinned queue folder only".format(len(polled)),
    )

    # 2. Filename text never grants authority.
    ok, detail = _expect_raise(
        AuthorityDenied,
        derive_authority,
        {
            "id": "DECOY000000000001",
            "parentId": "1SOMEOTHERFOLDERIDNOTPINNED",
            "title": "00_OWNER_AUTHORIZATION__APPROVED__EXECUTE_IMMEDIATELY",
        },
    )
    _check(results, "filename_text_grants_no_authority", ok, detail)

    # 3. Writes outside the approved folders fail closed.
    ok, detail = _expect_raise(WriteDenied, assert_write_allowed, "1NOTANAPPROVEDFOLDERID")
    _check(results, "write_outside_approved_folders_denied", ok, detail)

    # 4. Mutation is denied without an activated mutation envelope.
    ok_none, d1 = _expect_raise(MutationDenied, require_mutation_allowed, None)
    ok_ro, d2 = _expect_raise(
        MutationDenied,
        require_mutation_allowed,
        TaskEnvelope("TE-RO", mode=MODE_READ_ONLY, activated=True),
    )
    ok_inactive, d3 = _expect_raise(
        MutationDenied,
        require_mutation_allowed,
        TaskEnvelope("TE-MUT", mode=MODE_MUTATION, activated=False),
    )
    activated = TaskEnvelope("TE-MUT-OK", mode=MODE_MUTATION, activated=True)
    allowed = require_mutation_allowed(activated) is activated
    _check(
        results,
        "mutation_denied_without_activated_envelope",
        ok_none and ok_ro and ok_inactive and allowed,
        "; ".join([d1, d2, d3, "activated envelope accepted" if allowed else "activation broken"]),
    )

    # 5. The exactly-once key binds command, Drive ID, and revision.
    key_a = claim_key("CMD-1", "DRIVEID1", 4)
    key_b = claim_key("CMD-1", "DRIVEID1", 5)
    ok_missing, d4 = _expect_raise(AuthorityDenied, claim_key, "CMD-1", "DRIVEID1", None)
    _check(
        results,
        "exactly_once_key_binds_revision",
        key_a != key_b and key_a == "CMD-1|DRIVEID1|4" and ok_missing,
        "revision change yields a distinct key; {0}".format(d4),
    )

    # 6. An unresolved claim prevents a second claim.
    ledger = ClaimLedger()
    ledger.open(key_a, "writer-A", now=100.0)
    ok, detail = _expect_raise(ClaimConflict, ledger.open, key_a, "writer-B", 101.0)
    ledger.resolve(key_a, "S32_AUTHORITY_REISSUE_COMPILATION_BLOCKED")
    ok_after, detail_after = _expect_raise(ClaimConflict, ledger.open, key_a, "writer-C", 102.0)
    _check(
        results,
        "unresolved_claim_blocks_second_claim",
        ok and ok_after,
        "{0}; after terminalization: {1}".format(detail, detail_after),
    )

    # 7. A stale lease cannot write.
    fencing = FencingRegistry()
    leases = LeaseRegistry(fencing)
    lease = leases.acquire("section32", "writer-A", now=0.0, ttl_seconds=60)
    ok, detail = _expect_raise(LeaseExpired, leases.require_valid, lease, 120.0)
    still_valid = leases.require_valid(lease, 30.0) is lease
    _check(
        results,
        "stale_lease_cannot_write",
        ok and still_valid,
        "{0}; lease valid inside its window".format(detail),
    )

    # 8. Monotonic fencing is enforced.
    leases.release(lease)
    lease2 = leases.acquire("section32", "writer-B", now=200.0, ttl_seconds=60)
    ok, detail = _expect_raise(
        FencingViolation, fencing.require_strictly_current, "section32", lease.fencing_sequence
    )
    monotonic = lease2.fencing_sequence > lease.fencing_sequence
    _check(
        results,
        "monotonic_fencing_enforced",
        ok and monotonic,
        "{0}; sequence advanced {1} -> {2}".format(
            detail, lease.fencing_sequence, lease2.fencing_sequence
        ),
    )

    # 9. The spool is append-only and collision-safe.
    spool2 = AppendOnlySpool(os.path.join(root, "spool2"))
    spool2.put_record("rec.json", b"first")
    ok, detail = _expect_raise(SpoolCollision, spool2.put_record, "rec.json", b"second")
    preserved = open(os.path.join(spool2.root, "rec.json"), "rb").read() == b"first"
    _check(
        results,
        "spool_append_only_and_collision_safe",
        ok and preserved,
        "{0}; original bytes preserved".format(detail),
    )

    # 10. A Drive outage neither drops nor overwrites a receipt.
    client3 = OfflineDriveClient()
    spool3 = AppendOnlySpool(os.path.join(root, "spool3"))
    writer3 = SafeDriveWriter(client3, spool3)
    client3.outage = True
    outage_raised, d5 = _expect_raise(
        DriveOutage, writer3.emit_record, RECEIPTS_FOLDER_ID, "receipt.json", {"a": 1}
    )
    spooled_path = os.path.join(spool3.root, "receipt.json")
    retained = os.path.exists(spooled_path)
    pending = any(
        entry.get("event") == "UPLOAD_PENDING_DRIVE_OUTAGE" for entry in spool3.read_journal()
    )
    client3.outage = False
    ok_retry, d6 = _expect_raise(
        SpoolCollision, writer3.emit_record, RECEIPTS_FOLDER_ID, "receipt.json", {"a": 1}
    )
    _check(
        results,
        "drive_outage_does_not_drop_or_overwrite",
        outage_raised and retained and pending and ok_retry,
        "spooled before upload, marked pending, and re-emit refused to overwrite",
    )

    # 11. Secret values are redacted.
    # Built at runtime so no credential-shaped literal is committed, which
    # keeps the repository secret scanner armed without an allowlist blind spot.
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    fake_token = "gh" "p_" + (alphabet * 2)[:36]
    fake_password = "pw" + alphabet[:14]
    sample = 'token="{0}" and password: {1}'.format(fake_token, fake_password)
    scrubbed = redact(sample)
    _check(
        results,
        "secrets_redacted",
        fake_token not in scrubbed and fake_password not in scrubbed and "token" in scrubbed,
        "values removed, keys retained",
    )

    # 12. Protected workbooks and source evidence cannot be uploaded.
    ok_zip, d7 = _expect_raise(ProtectedArtifactUpload, assert_uploadable, b"PK\x03\x04rest")
    ok_ext, d8 = _expect_raise(
        ProtectedArtifactUpload, assert_uploadable, b"{}", "SECTION32.xlsx", "application/json"
    )
    ok_mime, d9 = _expect_raise(
        ProtectedArtifactUpload, assert_uploadable, b"{}", "x.json", "application/pdf"
    )
    _check(
        results,
        "protected_artifacts_cannot_be_uploaded",
        ok_zip and ok_ext and ok_mime,
        "; ".join([d7, d8, d9]),
    )

    # 13. The HOLD cannot be removed or altered.
    ok_alter, d10 = _expect_raise(HoldViolation, stamp_hold, {"hold": "RELEASED"})
    stamped = stamp_hold({"x": 1})
    ok_removed, d11 = _expect_raise(HoldViolation, assert_hold_intact, {"x": 1})
    _check(
        results,
        "hold_immutable",
        ok_alter and stamped["hold"] == HOLD and ok_removed,
        "{0}; {1}".format(d10, d11),
    )

    # 14. Canonical URLs are built from verified IDs only.
    url = canonical_drive_url("1C0C8ERuCYm6Rqso0ahLXMifhXqlYjinOlFkN5k29NCE")
    ok_bad, d12 = _expect_raise(UntrustedUrl, canonical_drive_url, "../../evil")
    _check(
        results,
        "canonical_urls_from_verified_ids_only",
        url.startswith("https://drive.google.com/file/d/") and ok_bad,
        d12,
    )

    # 15. Non-Google URLs are never trusted.
    ok_doci, d13 = _expect_raise(
        UntrustedUrl, assert_trusted_url, "https://docichat.com/open?state=abc"
    )
    ok_poll, d14 = _expect_raise(UntrustedUrl, assert_trusted_url, "https://livepolls.app/x")
    trusted = assert_trusted_url("https://drive.google.com/file/d/ABCDEFGHIJ/view")
    _check(
        results,
        "non_google_urls_never_trusted",
        ok_doci and ok_poll and bool(trusted),
        "{0}; {1}".format(d13, d14),
    )

    # 16. Reads outside the control package are refused.
    ok, detail = _expect_raise(ReadDenied, assert_read_allowed, "1SOMERANDOMFOLDERID")
    _check(results, "read_outside_control_package_denied", ok, detail)

    # 17. A verified round trip actually succeeds.
    client4 = OfflineDriveClient()
    spool4 = AppendOnlySpool(os.path.join(root, "spool4"))
    writer4 = SafeDriveWriter(client4, spool4)
    emitted = writer4.emit_record(RECEIPTS_FOLDER_ID, "ok.json", {"kind": "test"})
    _check(
        results,
        "verified_round_trip_succeeds",
        emitted["byte_exact_match"] and emitted["sha256"] == emitted["readback_sha256"],
        "uploaded and read back {0} bytes".format(emitted["uploaded_bytes"]),
    )

    # 18. A corrupted readback is detected rather than accepted.
    client5 = OfflineDriveClient()
    client5.corrupt_readback = True
    spool5 = AppendOnlySpool(os.path.join(root, "spool5"))
    writer5 = SafeDriveWriter(client5, spool5)
    ok, detail = _expect_raise(
        ReadbackMismatch, writer5.emit_record, RECEIPTS_FOLDER_ID, "corrupt.json", {"k": 1}
    )
    _check(results, "corrupted_readback_detected", ok, detail)

    # 19. Spent and retired commands are strictly rejected.
    ok_spent_id, d_spent_id = _expect_raise(
        RetiredCommandDenied,
        derive_authority,
        {"id": RETIRED_GATE0_COMMAND_DRIVE_ID, "parentId": QUEUE_FOLDER_ID},
    )
    ok_spent_cmd, d_spent_cmd = _expect_raise(
        RetiredCommandDenied,
        derive_authority,
        {"id": "SOMEOTHERID", "command_id": RETIRED_GATE0_COMMAND_ID, "parentId": QUEUE_FOLDER_ID},
    )
    _check(
        results,
        "spent_commands_strictly_rejected",
        ok_spent_id and ok_spent_cmd,
        "refused retired Gate 0 Drive ID and command ID per owner ruling",
    )

    # 20. State machine transitions are enforced.
    sm_valid = StateMachine.validate_command_transition("QUEUED", "CLAIMED") == "CLAIMED"
    ok_sm_illegal, d_sm = _expect_raise(
        StateMachineViolation,
        StateMachine.validate_command_transition,
        "TERMINALIZED",
        "CLAIMED",
    )
    _check(
        results,
        "state_machine_transitions_enforced",
        sm_valid and ok_sm_illegal,
        "valid transition accepted; illegal transition from terminal refused",
    )

    # 21. Heartbeat timeout is enforced.
    hb = HeartbeatRegistry(default_timeout_seconds=10.0)
    hb.pulse("L-TEST-1", now=100.0)
    hb_live = hb.check("L-TEST-1", now=105.0)
    ok_hb_exp, d_hb = _expect_raise(HeartbeatExpired, hb.check, "L-TEST-1", now=120.0)
    _check(
        results,
        "heartbeat_timeout_enforced",
        hb_live and ok_hb_exp,
        "pulse valid within window; {0}".format(d_hb),
    )

    # 22. Emergency stop flag halts operations immediately.
    stop = StopFlag()
    stop.trigger("Automated test emergency stop")
    ok_stop, d_stop = _expect_raise(StopFlagTriggered, stop.require_not_stopped)
    stop.clear()
    stop_cleared = stop.require_not_stopped()
    _check(
        results,
        "emergency_stop_flag_halts_operations",
        ok_stop and stop_cleared,
        "asserted stop raises; cleared stop allows execution",
    )

    # 23. Output allowlist is strictly enforced.
    allowed_set = frozenset({RECEIPTS_FOLDER_ID})
    out_ok = assert_output_allowed(RECEIPTS_FOLDER_ID, allowed_outputs=allowed_set) == RECEIPTS_FOLDER_ID
    ok_out_bad, d_out = _expect_raise(
        OutputNotAllowed,
        assert_output_allowed,
        STATUS_FOLDER_ID,
        allowed_outputs=allowed_set,
    )
    _check(
        results,
        "output_allowlist_enforced",
        out_ok and ok_out_bad,
        "folder in allowlist permitted; folder outside allowlist refused",
    )

    # 24. Receipt .sha256 sidecars are emitted and verified.
    client6 = OfflineDriveClient()
    spool6 = AppendOnlySpool(os.path.join(root, "spool6"))
    writer6 = SafeDriveWriter(client6, spool6)
    sidecar_res = writer6.emit_record_with_sidecar(
        RECEIPTS_FOLDER_ID, "sidecar_test.json", {"data": "test_sidecar"}
    )
    sidecar_ok = (
        "sidecar" in sidecar_res
        and sidecar_res["sidecar"]["byte_exact_match"] is True
        and os.path.exists(os.path.join(spool6.root, "sidecar_test.json.sha256"))
    )
    _check(
        results,
        "receipt_sha256_sidecars_verified",
        sidecar_ok,
        "record and .sha256 sidecar both uploaded, read back, and spooled",
    )

    # 25. Durable spool crash recovery resumes pending uploads.
    client7 = OfflineDriveClient()
    spool7 = AppendOnlySpool(os.path.join(root, "spool7"))
    writer7 = SafeDriveWriter(client7, spool7)
    client7.outage = True
    try:
        writer7.emit_record(RECEIPTS_FOLDER_ID, "outage_rec.json", {"recovery": True})
    except DriveOutage:
        pass
    client7.outage = False
    recovered = writer7.recover_pending_uploads()
    _check(
        results,
        "durable_spool_crash_recovery_resumes",
        len(recovered) == 1 and recovered[0]["byte_exact_match"] is True,
        "pending record recovered from local spool after outage and verified",
    )

    # 26. Rollback after partial failure is durably recorded in journal.
    spool8 = AppendOnlySpool(os.path.join(root, "spool8"))
    rollback_entry = spool8.rollback("partial_item.json", "Simulated partial failure")
    journal_entries = spool8.read_journal()
    _check(
        results,
        "rollback_recorded_in_journal",
        rollback_entry["event"] == "ROLLBACK_RECORDED"
        and any(e.get("event") == "ROLLBACK_RECORDED" for e in journal_entries),
        "rollback event journaled append-only with reason and HOLD stamped",
    )

    passed = sum(1 for r in results if r["passed"])
    return {
        "suite": "control_tower_selftest",
        "checks": results,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "ok": passed == len(results),
        "drive_writes": 0,
        "protected_artifact_mutations": 0,
        "hold": HOLD,
    }


def offline_canary():
    """A small, fast subset that must hold with no network of any kind."""
    report = selftest()
    wanted = (
        "only_canonical_queue_polled",
        "filename_text_grants_no_authority",
        "mutation_denied_without_activated_envelope",
        "stale_lease_cannot_write",
        "monotonic_fencing_enforced",
        "drive_outage_does_not_drop_or_overwrite",
        "non_google_urls_never_trusted",
    )
    picked = [c for c in report["checks"] if c["name"] in wanted]
    passed = sum(1 for c in picked if c["passed"])
    return {
        "suite": "control_tower_offline_canary",
        "checks": picked,
        "total": len(picked),
        "passed": passed,
        "failed": len(picked) - passed,
        "ok": passed == len(picked),
        "network_calls": 0,
        "hold": HOLD,
    }


def process_identity():
    """Deterministic identity bound into every claim receipt."""
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001 - getuser can fail in bare containers
        user = "unknown"
    return {
        "hostname": socket.gethostname(),
        "system": platform.system(),
        "is_windows": platform.system().lower().startswith("win"),
        "user": user,
        "pid": os.getpid(),
        "ppid": os.getppid() if hasattr(os, "getppid") else None,
        "executable": sys.executable,
    }


class Gate0Runner(object):
    """Claim exactly once, execute read-only, terminalize exactly once."""

    def __init__(
        self,
        writer,
        ledger=None,
        leases=None,
        heartbeats=None,
        stop_flag=None,
        scope="section32",
    ):
        self.writer = writer
        self.ledger = ledger or ClaimLedger()
        self.leases = leases or getattr(writer, "leases", None) or LeaseRegistry()
        self.heartbeats = heartbeats or getattr(writer, "heartbeats", None) or HeartbeatRegistry()
        self.stop_flag = stop_flag or getattr(writer, "stop_flag", None)
        self.scope = scope
        self._command_states = {}

    def preflight(self):
        """Refuse to claim unless the build itself passes its own selftest."""
        if self.stop_flag is not None:
            self.stop_flag.require_not_stopped()
        report = selftest()
        if not report["ok"]:
            raise ControlTowerError(
                "selftest failed {0}/{1}; refusing to claim".format(
                    report["failed"], report["total"]
                )
            )
        return report

    def claim(
        self,
        command_meta,
        command_revision,
        holder,
        now=None,
        ttl_seconds=900,
        allowed_outputs=None,
    ):
        if self.stop_flag is not None:
            self.stop_flag.require_not_stopped()
        now = time.time() if now is None else now
        authority = derive_authority(command_meta)
        command_id = command_meta.get("command_id") or command_meta["id"]
        key = claim_key(command_id, authority["command_drive_id"], command_revision)

        claim = self.ledger.open(key, holder, now)
        current_state = self._command_states.get(key, "QUEUED")
        StateMachine.validate_command_transition(current_state, "CLAIMED")

        lease = self.leases.acquire(self.scope, holder, now, ttl_seconds)
        self.heartbeats.pulse(lease.lease_id, now)
        receipt = stamp_hold(
            {
                "schema": "databossx.gate0_start_claim.v1",
                "receipt_type": "GATE0_START_CLAIM",
                "command_id": command_id,
                "command_drive_id": authority["command_drive_id"],
                "command_revision": command_revision,
                "authority_source": authority["authority_source"],
                "title_considered_for_authority": False,
                "claim_key": key,
                "lease_id": lease.lease_id,
                "lease_expires_at": lease.expires_at,
                "fencing_sequence": lease.fencing_sequence,
                "mode": MODE_READ_ONLY,
                "mutation_permitted": False,
                "process": process_identity(),
                "started_at_epoch": now,
                "allowed_write_folder_ids": sorted(ALLOWED_WRITE_FOLDER_IDS),
                "stop_conditions": [
                    "selftest failure",
                    "hash mismatch",
                    "competing writer",
                    "stale lease",
                    "fencing violation",
                    "readback mismatch",
                    "prohibited path",
                    "heartbeat timeout",
                    "emergency stop flag",
                ],
            }
        )
        try:
            emitted = self.writer.emit_record_with_sidecar(
                RECEIPTS_FOLDER_ID,
                "DBX_RECEIPT__GATE0_START_CLAIM__{0}.json".format(key.replace("|", "__")),
                receipt,
                lease=lease,
                now=now,
                allowed_outputs=allowed_outputs,
                stop_flag=self.stop_flag,
            )
            self._command_states[key] = "CLAIMED"
            return {"claim": claim, "lease": lease, "receipt": emitted, "claim_key": key}
        except Exception as exc:
            self.writer.spool.rollback(
                "DBX_RECEIPT__GATE0_START_CLAIM__{0}.json".format(key.replace("|", "__")),
                "Claim emission failed: {0}".format(exc),
            )
            raise

    def terminalize(
        self,
        claim_key_value,
        sentinel,
        findings,
        lease=None,
        now=None,
        allowed_outputs=None,
    ):
        if self.stop_flag is not None:
            self.stop_flag.require_not_stopped()
        if sentinel not in GATE0_TERMINAL_SENTINELS:
            raise ControlTowerError("not a Gate 0 terminal sentinel: {0}".format(sentinel))
        now = time.time() if now is None else now

        resolved = self.ledger.resolve(claim_key_value, sentinel)
        current_state = self._command_states.get(claim_key_value, "AUDITING")
        StateMachine.validate_command_transition(current_state, "TERMINALIZED")

        receipt = stamp_hold(
            {
                "schema": "databossx.gate0_terminal.v1",
                "receipt_type": "GATE0_TERMINAL",
                "claim_key": claim_key_value,
                "terminal_sentinel": sentinel,
                "findings": findings,
                "workbook_mutated": False,
                "ended_at_epoch": now,
            }
        )
        try:
            emitted = self.writer.emit_record_with_sidecar(
                RECEIPTS_FOLDER_ID,
                "DBX_RECEIPT__GATE0_TERMINAL__{0}.json".format(
                    claim_key_value.replace("|", "__")
                ),
                receipt,
                lease=lease,
                now=now,
                allowed_outputs=allowed_outputs,
                stop_flag=self.stop_flag,
            )
            self._command_states[claim_key_value] = "TERMINALIZED"
            if lease is not None:
                self.leases.release(lease)
                self.heartbeats.clear(lease.lease_id)
            return {"claim": resolved, "receipt": emitted}
        except Exception as exc:
            self.writer.spool.rollback(
                "DBX_RECEIPT__GATE0_TERMINAL__{0}.json".format(
                    claim_key_value.replace("|", "__")
                ),
                "Terminalize emission failed: {0}".format(exc),
            )
            raise

    def execute_read_only(self, **audit_kwargs):
        """Gate 0 proper. Read-only by construction; opens no workbook."""
        if self.stop_flag is not None:
            self.stop_flag.require_not_stopped()
        report = run_audit(client=self.writer.client, **audit_kwargs)
        report["digest"] = sha256_hex(canonical_json_bytes(report))
        return report
