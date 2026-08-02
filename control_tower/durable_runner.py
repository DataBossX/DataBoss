"""Crash-safe Gate 0 runner backed by durable claims, leases and fencing.

This runner is additive while the original PR #74 runner remains available for
read-only compatibility. Live claim and terminal work must use this class.
"""

import time

from .audit import run_audit
from .constants import (
    ALLOWED_WRITE_FOLDER_IDS,
    GATE0_TERMINAL_SENTINELS,
    MODE_READ_ONLY,
    RECEIPTS_FOLDER_ID,
    ControlTowerError,
    SpoolCollision,
)
from .kernel import claim_key, derive_authority
from .safety import canonical_json_bytes, sha256_hex, stamp_hold
from .tower import process_identity, selftest


class DurableGate0Runner(object):
    """Prepare, upload, verify and commit every transition in safe order."""

    def __init__(self, writer, ledger, leases, scope="section32"):
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

    def preflight(self):
        report = selftest()
        if not report["ok"]:
            raise ControlTowerError(
                "selftest failed {0}/{1}; refusing to claim".format(
                    report["failed"], report["total"]
                )
            )
        return report

    @staticmethod
    def _emit_or_recover(writer, folder_id, name, record, lease, now):
        try:
            return writer.emit_record(
                folder_id, name, record, lease=lease, now=now
            )
        except SpoolCollision:
            return writer.recover_record(
                folder_id, name, lease=lease, now=now
            )

    def claim(self, command_meta, command_revision, holder, now=None, ttl_seconds=900):
        self.preflight()
        now = time.time() if now is None else float(now)
        authority = derive_authority(command_meta)
        command_id = command_meta.get("command_id") or command_meta["id"]
        key = claim_key(command_id, authority["command_drive_id"], command_revision)
        receipt_name = "DBX_RECEIPT__GATE0_START_CLAIM__{0}.json".format(
            key.replace("|", "__")
        )
        lease = self.leases.acquire(self.scope, holder, now, ttl_seconds)
        existing = self.ledger.state(key)
        if (
            existing
            and existing.get("state") == "OPEN"
            and existing.get("holder") == holder
            and existing.get("start_receipt_name") == receipt_name
        ):
            prepared = existing
        else:
            prepared = self.ledger.prepare_open(
                key, holder, now, receipt_name=receipt_name
            )
        receipt = stamp_hold(
            {
                "schema": "databossx.gate0_start_claim.v2",
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
                "started_at_epoch": prepared.get("opened_at", now),
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
        emitted = self._emit_or_recover(
            self.writer,
            RECEIPTS_FOLDER_ID,
            receipt_name,
            receipt,
            lease,
            now,
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

    def terminalize(self, claim_key_value, sentinel, findings, lease, now=None):
        if sentinel not in GATE0_TERMINAL_SENTINELS:
            raise ControlTowerError("not a Gate 0 terminal sentinel: {0}".format(sentinel))
        now = time.time() if now is None else float(now)
        receipt_name = "DBX_RECEIPT__GATE0_TERMINAL__{0}.json".format(
            claim_key_value.replace("|", "__")
        )
        existing = self.ledger.state(claim_key_value)
        if (
            existing
            and existing.get("state") in ("TERMINAL_PREPARED", "TERMINAL_UPLOADED")
            and existing.get("sentinel") == sentinel
            and existing.get("terminal_name") == receipt_name
        ):
            prepared = existing
        else:
            prepared = self.ledger.prepare_terminal(
                claim_key_value, sentinel, receipt_name
            )
        receipt = stamp_hold(
            {
                "schema": "databossx.gate0_terminal.v2",
                "receipt_type": "GATE0_TERMINAL",
                "claim_key": claim_key_value,
                "terminal_sentinel": sentinel,
                "findings": findings,
                "workbook_mutated": False,
                "ended_at_epoch": now,
            }
        )
        emitted = self._emit_or_recover(
            self.writer,
            RECEIPTS_FOLDER_ID,
            receipt_name,
            receipt,
            lease,
            now,
        )
        uploaded = self.ledger.mark_terminal_uploaded(
            claim_key_value, emitted["drive_id"], emitted["sha256"]
        )
        resolved = self.ledger.resolve_terminal(claim_key_value)
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
