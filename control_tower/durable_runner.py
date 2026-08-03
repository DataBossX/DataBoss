"""Crash-safe Gate 0 runner backed by durable claims, leases and fencing.

This runner is additive while the original PR #74 runner remains available for
read-only compatibility. Live claim and terminal work must use this class.
Every receipt's exact expected digest is committed to durable claim state
before local spooling or a Drive request, so restart recovery cannot adopt
changed, stale or tampered spool bytes.
"""

import time

from .audit import run_audit
from .constants import (
    ALLOWED_WRITE_FOLDER_IDS,
    GATE0_TERMINAL_SENTINELS,
    MODE_READ_ONLY,
    RECEIPTS_FOLDER_ID,
    ClaimConflict,
    ControlTowerError,
    FencingViolation,
    LeaseExpired,
    SpoolCollision,
)
from .kernel import (
    Lease,
    TaskEnvelope,
    WriterACK,
    claim_key,
    derive_authority,
    require_mutation_allowed,
)
from .reconstruction import reject_noncanonical_package
from .safety import canonical_json_bytes, sha256_hex, stamp_hold
from .tower import process_identity, selftest


class DurableGate0Runner(object):
    """Prepare, upload, verify and commit every transition in safe order."""

    def __init__(
        self, writer, ledger, leases, scope="section32", startup_reconstructor=None
    ):
        if writer.leases is None:
            writer.leases = leases
        if writer.leases is not leases:
            raise ControlTowerError("runner and writer must share one lease registry")
        if getattr(ledger, "store", None) is None:
            raise ControlTowerError("durable runner requires a durable claim ledger")
        if getattr(leases, "store", None) is None:
            raise ControlTowerError("durable runner requires a durable lease registry")
        if ledger.store is not leases.store:
            raise ControlTowerError("claim and lease registries must share one durable store")
        writer.bind_durable_runner(leases.store)
        self.writer = writer
        self.ledger = ledger
        self.leases = leases
        self.scope = scope
        self.startup_reconstructor = startup_reconstructor

    def preflight(self):
        report = selftest()
        if not report["ok"]:
            raise ControlTowerError(
                "selftest failed {0}/{1}; refusing to claim".format(
                    report["failed"], report["total"]
                )
            )
        return report

    def _ensure_startup_reconstructed(self):
        if self.writer.client.is_offline:
            return None
        if self.startup_reconstructor is None:
            raise ControlTowerError(
                "live transition requires exact canonical startup reconstruction"
            )
        return self.startup_reconstructor.ensure_reconstructed()

    def _validate_authority(self, envelope, ack, holder, now):
        """Validate one activated envelope and matching single-use ACK."""
        if self.writer.client.is_offline and envelope is None and ack is None:
            return None
        require_mutation_allowed(envelope)
        if not isinstance(envelope, TaskEnvelope):
            raise ControlTowerError("live transition requires a TaskEnvelope")
        if not isinstance(ack, WriterACK):
            raise ControlTowerError("live transition requires a WriterACK")
        body = envelope.body
        required = (
            "actor",
            "operation",
            "scope",
            "input_hashes",
            "control_hashes",
            "output_allowlist",
            "expires_at",
        )
        missing = [name for name in required if body.get(name) in (None, "")]
        if missing:
            raise ControlTowerError(
                "TaskEnvelope missing required bindings: {0}".format(
                    ", ".join(sorted(missing))
                )
            )
        if float(body["expires_at"]) <= float(now):
            raise ControlTowerError("TaskEnvelope is expired")
        if not isinstance(body["input_hashes"], dict) or not body["input_hashes"]:
            raise ControlTowerError("TaskEnvelope input_hashes must be a non-empty mapping")
        if not isinstance(body["control_hashes"], dict) or not body["control_hashes"]:
            raise ControlTowerError("TaskEnvelope control_hashes must be a non-empty mapping")
        if not isinstance(body["output_allowlist"], (list, tuple)) or not body[
            "output_allowlist"
        ]:
            raise ControlTowerError("TaskEnvelope output_allowlist must be non-empty")
        if body["actor"] != holder or body["scope"] != self.scope:
            raise ControlTowerError("TaskEnvelope actor or scope mismatch")
        if RECEIPTS_FOLDER_ID not in tuple(body["output_allowlist"]):
            raise ControlTowerError("TaskEnvelope output allowlist excludes receipts")
        if ack.envelope_digest != envelope.digest:
            raise ControlTowerError("WriterACK envelope digest mismatch")
        if (
            ack.actor != holder
            or ack.operation != body["operation"]
            or ack.scope != self.scope
            or ack.expires_at <= float(now)
        ):
            raise ControlTowerError("WriterACK actor, operation, scope, or expiry mismatch")
        return {
            "envelope_id": envelope.envelope_id,
            "envelope_digest": envelope.digest,
            "ack": ack.as_record(),
            "operation": body["operation"],
        }

    @staticmethod
    def _valid_lease_from_state(state, scope, lease, holder, now):
        record = state["leases"].get(scope)
        if record is None:
            raise LeaseExpired("no durable active lease for {0}".format(scope))
        current = Lease.from_record(record)
        if (
            current.lease_id != lease.lease_id
            or current.holder != holder
            or current.fencing_sequence != lease.fencing_sequence
        ):
            raise LeaseExpired("lease identity, holder, or fence is stale")
        if current.released or float(now) >= current.expires_at:
            raise LeaseExpired("lease is released or expired")
        if int(state["fencing"].get(scope, 0)) != current.fencing_sequence:
            raise FencingViolation("lease fence is not strictly current")
        return current

    def _issue_lease_in_state(self, state, holder, now, ttl_seconds):
        current_record = state["leases"].get(self.scope)
        if current_record:
            current = Lease.from_record(current_record)
            if current.is_valid(now):
                if current.holder != holder:
                    raise ClaimConflict(
                        "scope {0} is leased by {1}".format(self.scope, current.holder)
                    )
                return current
        sequence = int(state["fencing"].get(self.scope, 0)) + 1
        state["fencing"][self.scope] = sequence
        lease = Lease(
            "LEASE-{0}-{1}".format(self.scope, sequence),
            self.scope,
            holder,
            float(now) + float(ttl_seconds),
            sequence,
        )
        state["leases"][self.scope] = lease.as_record()
        return lease

    @staticmethod
    def _consume_or_validate_ack(state, authority, key):
        if authority is None:
            return
        ack = authority["ack"]
        existing = state["writer_acks"].get(ack["ack_id"])
        bound = dict(ack)
        bound.update(
            {
                "envelope_id": authority["envelope_id"],
                "consumed": True,
                "consumed_by": key,
            }
        )
        if existing is None:
            state["writer_acks"][ack["ack_id"]] = bound
            return
        if existing != bound:
            raise ClaimConflict("WriterACK is replayed, changed, or bound to another claim")

    @staticmethod
    def _emit_or_recover(
        writer, folder_id, name, record, lease, now, expected_sha256
    ):
        try:
            return writer.emit_record(
                folder_id, name, record, lease=lease, now=now
            )
        except SpoolCollision:
            return writer.recover_record(
                folder_id,
                name,
                lease=lease,
                now=now,
                expected_sha256=expected_sha256,
            )

    def claim(
        self,
        command_meta,
        command_revision,
        holder,
        now=None,
        ttl_seconds=900,
        task_envelope=None,
        writer_ack=None,
        recover_expired=False,
    ):
        self.preflight()
        now = time.time() if now is None else float(now)
        reject_noncanonical_package(command_meta)
        authority_binding = self._validate_authority(
            task_envelope, writer_ack, holder, now
        )
        self._ensure_startup_reconstructed()
        authority = derive_authority(command_meta)
        command_id = command_meta.get("command_id") or command_meta["id"]
        key = claim_key(command_id, authority["command_drive_id"], command_revision)
        receipt_name = "DBX_RECEIPT__GATE0_START_CLAIM__{0}.json".format(
            key.replace("|", "__")
        )

        def mutate(state):
            if state["retired_commands"].get(command_id):
                raise ClaimConflict("command {0} is retired and spent".format(command_id))
            existing = state["claims"].get(key)
            if existing is not None:
                if (
                    existing.get("holder") != holder
                    or existing.get("start_receipt_name") != receipt_name
                    or existing.get("state") not in ("CLAIM_PREPARED", "OPEN")
                ):
                    raise ClaimConflict("claim {0} already exists incompatibly".format(key))
                current_record = state["leases"].get(self.scope)
                current = Lease.from_record(current_record) if current_record else None
                if current is None or not current.is_valid(now) or current.holder != holder:
                    if not recover_expired:
                        raise LeaseExpired(
                            "prepared START requires explicit expired-lease recovery"
                        )
                    lease_value = self._issue_lease_in_state(
                        state, holder, now, ttl_seconds
                    )
                    existing = dict(existing)
                    existing["recovery_lease_id"] = lease_value.lease_id
                    existing["recovery_fencing_sequence"] = lease_value.fencing_sequence
                    state["claims"][key] = existing
                else:
                    lease_value = current
                self._consume_or_validate_ack(state, authority_binding, key)
                return dict(existing), lease_value, dict(existing["start_receipt_payload"])

            self._consume_or_validate_ack(state, authority_binding, key)
            lease_value = self._issue_lease_in_state(state, holder, now, ttl_seconds)
            receipt_value = stamp_hold(
                {
                    "schema": "databossx.gate0_start_claim.v2",
                    "receipt_type": "GATE0_START_CLAIM",
                    "command_id": command_id,
                    "command_drive_id": authority["command_drive_id"],
                    "command_revision": command_revision,
                    "authority_source": authority["authority_source"],
                    "title_considered_for_authority": False,
                    "claim_key": key,
                    "lease_id": lease_value.lease_id,
                    "lease_expires_at": lease_value.expires_at,
                    "fencing_sequence": lease_value.fencing_sequence,
                    "task_envelope_digest": None
                    if authority_binding is None
                    else authority_binding["envelope_digest"],
                    "writer_ack_id": None
                    if authority_binding is None
                    else authority_binding["ack"]["ack_id"],
                    "mode": MODE_READ_ONLY,
                    "mutation_permitted": False,
                    "process": process_identity(),
                    "started_at_epoch": float(now),
                    "allowed_write_folder_ids": sorted(ALLOWED_WRITE_FOLDER_IDS),
                    "stop_conditions": [
                        "selftest failure",
                        "retired command",
                        "hash mismatch",
                        "competing writer",
                        "missing or stale lease",
                        "fencing violation",
                        "readback mismatch",
                        "duplicate Drive object",
                        "prohibited path",
                    ],
                }
            )
            digest = sha256_hex(canonical_json_bytes(receipt_value))
            prepared_value = {
                "key": key,
                "holder": holder,
                "opened_at": float(now),
                "state": "CLAIM_PREPARED",
                "sentinel": None,
                "start_receipt_name": receipt_name,
                "start_receipt_payload": receipt_value,
                "start_expected_sha256": digest,
                "task_envelope_digest": None
                if authority_binding is None
                else authority_binding["envelope_digest"],
                "writer_ack_id": None
                if authority_binding is None
                else authority_binding["ack"]["ack_id"],
            }
            state["claims"][key] = prepared_value
            return dict(prepared_value), lease_value, receipt_value

        prepared, lease, receipt = self.ledger.store.transaction(mutate)
        expected_digest = prepared["start_expected_sha256"]
        emitted = self._emit_or_recover(
            self.writer,
            RECEIPTS_FOLDER_ID,
            receipt_name,
            receipt,
            lease,
            now,
            expected_digest,
        )
        opened = self.ledger.mark_open(
            key, drive_id=emitted["drive_id"], digest=emitted["sha256"]
        )
        return {
            "claim": opened,
            "prepared": prepared,
            "lease": lease,
            "receipt": emitted,
            "claim_key": key,
        }

    def recover_start(
        self,
        command_meta,
        command_revision,
        holder,
        now=None,
        ttl_seconds=900,
        task_envelope=None,
        writer_ack=None,
    ):
        return self.claim(
            command_meta,
            command_revision,
            holder,
            now=now,
            ttl_seconds=ttl_seconds,
            task_envelope=task_envelope,
            writer_ack=writer_ack,
            recover_expired=True,
        )

    def terminalize(
        self,
        claim_key_value,
        sentinel,
        findings,
        lease,
        now=None,
        task_envelope=None,
        writer_ack=None,
    ):
        if sentinel not in GATE0_TERMINAL_SENTINELS:
            raise ControlTowerError("not a Gate 0 terminal sentinel: {0}".format(sentinel))
        now = time.time() if now is None else float(now)
        holder = lease.holder if lease is not None else ""
        authority_binding = self._validate_authority(
            task_envelope, writer_ack, holder, now
        )
        self._ensure_startup_reconstructed()
        receipt_name = "DBX_RECEIPT__GATE0_TERMINAL__{0}.json".format(
            claim_key_value.replace("|", "__")
        )
        existing_snapshot = self.ledger.state(claim_key_value)
        ended_at = (
            existing_snapshot.get("terminal_ended_at")
            if existing_snapshot
            and existing_snapshot.get("terminal_ended_at") is not None
            else now
        )
        receipt = stamp_hold(
            {
                "schema": "databossx.gate0_terminal.v2",
                "receipt_type": "GATE0_TERMINAL",
                "claim_key": claim_key_value,
                "terminal_sentinel": sentinel,
                "findings": findings,
                "workbook_mutated": False,
                "ended_at_epoch": ended_at,
            }
        )
        expected_digest = sha256_hex(canonical_json_bytes(receipt))

        def prepare(state):
            record = state["claims"].get(claim_key_value)
            if record is None:
                raise ClaimConflict("cannot terminalize unknown claim")
            self._valid_lease_from_state(state, self.scope, lease, holder, now)
            self._consume_or_validate_ack(state, authority_binding, claim_key_value)
            if authority_binding is not None and (
                record.get("task_envelope_digest") != authority_binding["envelope_digest"]
                or record.get("writer_ack_id") != authority_binding["ack"]["ack_id"]
            ):
                raise ClaimConflict("terminal authority does not match frozen claim authority")
            if record.get("state") in ("TERMINAL_PREPARED", "TERMINAL_UPLOADED"):
                if (
                    record.get("sentinel") != sentinel
                    or record.get("terminal_name") != receipt_name
                    or record.get("terminal_expected_sha256") != expected_digest
                ):
                    raise ClaimConflict("terminal preparation conflicts for {0}".format(claim_key_value))
                return dict(record), dict(record.get("terminal_receipt_payload") or receipt)
            if record.get("state") != "OPEN":
                raise ClaimConflict("claim is not OPEN for terminal preparation")
            record = dict(record)
            record.update(
                {
                    "state": "TERMINAL_PREPARED",
                    "sentinel": sentinel,
                    "terminal_name": receipt_name,
                    "terminal_ended_at": ended_at,
                    "terminal_expected_sha256": expected_digest,
                    "terminal_receipt_payload": receipt,
                    "terminal_lease_id": lease.lease_id,
                    "terminal_fencing_sequence": lease.fencing_sequence,
                }
            )
            state["claims"][claim_key_value] = record
            return dict(record), receipt

        prepared, receipt = self.ledger.store.transaction(prepare)
        emitted = self._emit_or_recover(
            self.writer,
            RECEIPTS_FOLDER_ID,
            receipt_name,
            receipt,
            lease,
            now,
            expected_digest,
        )

        def mark_uploaded(state):
            record = state["claims"].get(claim_key_value)
            self._valid_lease_from_state(state, self.scope, lease, holder, now)
            if record is None or record.get("state") not in (
                "TERMINAL_PREPARED",
                "TERMINAL_UPLOADED",
            ):
                raise ClaimConflict("terminal is not prepared")
            if emitted["sha256"] != record.get("terminal_expected_sha256"):
                raise ClaimConflict("uploaded terminal digest differs from frozen digest")
            record = dict(record)
            record.update(
                {
                    "state": "TERMINAL_UPLOADED",
                    "terminal_drive_id": emitted["drive_id"],
                    "terminal_sha256": emitted["sha256"],
                }
            )
            state["claims"][claim_key_value] = record
            return dict(record)

        uploaded = self.ledger.store.transaction(mark_uploaded)

        def resolve(state):
            record = state["claims"].get(claim_key_value)
            self._valid_lease_from_state(state, self.scope, lease, holder, now)
            if record is None or record.get("state") != "TERMINAL_UPLOADED":
                raise ClaimConflict("terminal is not uploaded")
            record = dict(record)
            record["state"] = "RESOLVED"
            state["claims"][claim_key_value] = record
            return dict(record)

        resolved = self.ledger.store.transaction(resolve)
        self.leases.release(lease)
        return {
            "prepared": prepared,
            "uploaded": uploaded,
            "claim": resolved,
            "receipt": emitted,
        }

    def retire_command(self, command_id, evidence=None):
        return self.ledger.retire_command(command_id, evidence=evidence)

    def execute_read_only(self, **audit_kwargs):
        report = run_audit(client=self.writer.client, **audit_kwargs)
        report["digest"] = sha256_hex(canonical_json_bytes(report))
        return report
