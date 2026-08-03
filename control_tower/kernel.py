"""The control kernel: authority, claims, leases, fencing, and the spool.

The invariants here are fail-closed.  When a :class:`DurableStateStore` is
supplied, claims, leases, fencing tokens and retired-command denials survive
process restart and are updated under one atomic transaction.
"""

import json
import os

from .constants import (
    MODE_MUTATION,
    MODE_READ_ONLY,
    POLLED_FOLDER_ID,
    AuthorityDenied,
    ClaimConflict,
    FencingViolation,
    LeaseExpired,
    MutationDenied,
    SpoolCollision,
)
from .safety import canonical_json_bytes, redact_tree, sha256_hex, stamp_hold


# --------------------------------------------------------------------------
# Authority
# --------------------------------------------------------------------------
def derive_authority(file_meta):
    """Decide whether a Drive file may act as a command.

    Authority comes from folder membership by pinned ID.  Filename text is
    display data only and never grants permission.
    """
    if not isinstance(file_meta, dict):
        raise AuthorityDenied("file metadata must be a mapping")
    parent = file_meta.get("parentId")
    file_id = file_meta.get("id")
    if not file_id:
        raise AuthorityDenied("file has no Drive ID")
    if parent != POLLED_FOLDER_ID:
        raise AuthorityDenied(
            "file {0} is not in the canonical queue folder".format(file_id)
        )
    return {
        "command_drive_id": file_id,
        "authority_source": "CANONICAL_QUEUE_FOLDER_MEMBERSHIP",
        "title_considered_for_authority": False,
    }


def claim_key(command_id, command_drive_id, command_revision):
    """Return the exactly-once key bound to command, Drive ID and revision."""
    for name, value in (
        ("command_id", command_id),
        ("command_drive_id", command_drive_id),
        ("command_revision", command_revision),
    ):
        if value is None or value == "":
            raise AuthorityDenied("claim key requires {0}".format(name))
    return "{0}|{1}|{2}".format(command_id, command_drive_id, command_revision)


# --------------------------------------------------------------------------
# TaskEnvelope and the mutation gate
# --------------------------------------------------------------------------
class TaskEnvelope(object):
    """A unit of authorized work. Mutation requires explicit activation."""

    def __init__(self, envelope_id, mode=MODE_READ_ONLY, activated=False, body=None):
        if mode not in (MODE_READ_ONLY, MODE_MUTATION):
            raise MutationDenied("unknown envelope mode: {0}".format(mode))
        self.envelope_id = envelope_id
        self.mode = mode
        self.activated = bool(activated)
        self.body = body or {}

    @property
    def digest(self):
        return sha256_hex(
            canonical_json_bytes(
                {
                    "envelope_id": self.envelope_id,
                    "mode": self.mode,
                    "activated": self.activated,
                    "body": self.body,
                }
            )
        )


class WriterACK(object):
    """Single-use writer acknowledgement bound to one TaskEnvelope.

    Consumption is persisted by :class:`DurableStateStore`; this value object
    intentionally carries no mutable ``consumed`` flag that a caller could
    reset in memory.
    """

    def __init__(
        self,
        ack_id,
        envelope_digest,
        actor,
        operation,
        scope,
        expires_at,
    ):
        self.ack_id = str(ack_id)
        self.envelope_digest = str(envelope_digest)
        self.actor = str(actor)
        self.operation = str(operation)
        self.scope = str(scope)
        self.expires_at = float(expires_at)

    def as_record(self):
        return {
            "ack_id": self.ack_id,
            "envelope_digest": self.envelope_digest,
            "actor": self.actor,
            "operation": self.operation,
            "scope": self.scope,
            "expires_at": self.expires_at,
        }


def require_mutation_allowed(envelope):
    """Fail closed unless an activated mutation envelope is presented."""
    if envelope is None:
        raise MutationDenied("mutation requires a TaskEnvelope; none supplied")
    if not isinstance(envelope, TaskEnvelope):
        raise MutationDenied("mutation requires a TaskEnvelope instance")
    if envelope.mode != MODE_MUTATION:
        raise MutationDenied(
            "envelope {0} is {1}, not a mutation envelope".format(
                envelope.envelope_id, envelope.mode
            )
        )
    if not envelope.activated:
        raise MutationDenied(
            "envelope {0} is not activated by the owner".format(envelope.envelope_id)
        )
    return envelope


# --------------------------------------------------------------------------
# Fencing
# --------------------------------------------------------------------------
class FencingRegistry(object):
    """Monotonic per-scope sequence with optional durable atomic storage."""

    def __init__(self, store=None):
        self.store = store
        self._highest = {}

    def next_sequence(self, scope):
        if self.store is None:
            nxt = self._highest.get(scope, 0) + 1
            self._highest[scope] = nxt
            return nxt

        def mutate(state):
            nxt = int(state["fencing"].get(scope, 0)) + 1
            state["fencing"][scope] = nxt
            return nxt

        return self.store.transaction(mutate)

    def highest(self, scope):
        if self.store is None:
            return self._highest.get(scope, 0)
        return int(self.store.read()["fencing"].get(scope, 0))

    def require(self, scope, sequence):
        if not isinstance(sequence, int):
            raise FencingViolation("fencing sequence must be an integer")
        current = self.highest(scope)
        if sequence < current:
            raise FencingViolation(
                "stale fencing sequence {0} for scope {1}; current is {2}".format(
                    sequence, scope, current
                )
            )
        return sequence

    def require_strictly_current(self, scope, sequence):
        current = self.highest(scope)
        if sequence != current or current == 0:
            raise FencingViolation(
                "fencing token {0} is not the current token {1} for {2}".format(
                    sequence, current, scope
                )
            )
        return sequence


# --------------------------------------------------------------------------
# Leases
# --------------------------------------------------------------------------
class Lease(object):
    def __init__(self, lease_id, scope, holder, expires_at, fencing_sequence, released=False):
        self.lease_id = lease_id
        self.scope = scope
        self.holder = holder
        self.expires_at = float(expires_at)
        self.fencing_sequence = int(fencing_sequence)
        self.released = bool(released)

    @classmethod
    def from_record(cls, record):
        return cls(
            lease_id=record["lease_id"],
            scope=record["scope"],
            holder=record["holder"],
            expires_at=record["expires_at"],
            fencing_sequence=record["fencing_sequence"],
            released=record.get("released", False),
        )

    def is_valid(self, now):
        return (not self.released) and float(now) < self.expires_at

    def as_record(self):
        return {
            "lease_id": self.lease_id,
            "scope": self.scope,
            "holder": self.holder,
            "expires_at": self.expires_at,
            "fencing_sequence": self.fencing_sequence,
            "released": self.released,
        }


class LeaseRegistry(object):
    """One active lease per scope, persisted with its fencing token."""

    def __init__(self, fencing=None, store=None):
        self.store = store or getattr(fencing, "store", None)
        self.fencing = fencing or FencingRegistry(store=self.store)
        if self.store is not None and self.fencing.store is not self.store:
            raise ClaimConflict("lease and fencing registries use different durable stores")
        self._active = {}

    def acquire(self, scope, holder, now, ttl_seconds):
        now = float(now)
        ttl_seconds = float(ttl_seconds)
        if ttl_seconds <= 0:
            raise LeaseExpired("lease TTL must be positive")
        if self.store is None:
            current = self._active.get(scope)
            if current is not None and current.is_valid(now):
                if current.holder != holder:
                    raise ClaimConflict(
                        "scope {0} is leased by {1} until {2}".format(
                            scope, current.holder, current.expires_at
                        )
                    )
                return current
            sequence = self.fencing.next_sequence(scope)
            lease = Lease(
                lease_id="LEASE-{0}-{1}".format(scope, sequence),
                scope=scope,
                holder=holder,
                expires_at=now + ttl_seconds,
                fencing_sequence=sequence,
            )
            self._active[scope] = lease
            return lease

        def mutate(state):
            current_record = state["leases"].get(scope)
            if current_record:
                current = Lease.from_record(current_record)
                if current.is_valid(now):
                    if current.holder != holder:
                        raise ClaimConflict(
                            "scope {0} is leased by {1} until {2}".format(
                                scope, current.holder, current.expires_at
                            )
                        )
                    return current
            sequence = int(state["fencing"].get(scope, 0)) + 1
            state["fencing"][scope] = sequence
            lease = Lease(
                lease_id="LEASE-{0}-{1}".format(scope, sequence),
                scope=scope,
                holder=holder,
                expires_at=now + ttl_seconds,
                fencing_sequence=sequence,
            )
            state["leases"][scope] = lease.as_record()
            return lease

        return self.store.transaction(mutate)

    def release(self, lease):
        if self.store is None:
            lease.released = True
            if self._active.get(lease.scope) is lease:
                del self._active[lease.scope]
            return lease

        def mutate(state):
            current = state["leases"].get(lease.scope)
            if not current or current.get("lease_id") != lease.lease_id:
                raise LeaseExpired("lease {0} is not the active lease".format(lease.lease_id))
            current = dict(current)
            current["released"] = True
            state["leases"][lease.scope] = current
            return Lease.from_record(current)

        released = self.store.transaction(mutate)
        lease.released = True
        return released

    def require_valid(self, lease, now):
        if lease is None:
            raise LeaseExpired("no lease supplied")
        now = float(now)
        if self.store is None:
            if not lease.is_valid(now):
                raise LeaseExpired(
                    "lease {0} expired at {1}; now is {2}".format(
                        lease.lease_id, lease.expires_at, now
                    )
                )
            self.fencing.require_strictly_current(lease.scope, lease.fencing_sequence)
            return lease

        state = self.store.read()
        current_record = state["leases"].get(lease.scope)
        if not current_record:
            raise LeaseExpired("no durable active lease for {0}".format(lease.scope))
        current = Lease.from_record(current_record)
        if current.lease_id != lease.lease_id or current.holder != lease.holder:
            raise LeaseExpired("lease identity or holder does not match durable state")
        if current.fencing_sequence != lease.fencing_sequence:
            raise FencingViolation("lease fencing token does not match durable state")
        if not current.is_valid(now):
            raise LeaseExpired(
                "lease {0} expired at {1}; now is {2}".format(
                    current.lease_id, current.expires_at, now
                )
            )
        self.fencing.require_strictly_current(current.scope, current.fencing_sequence)
        return current


# --------------------------------------------------------------------------
# Claims
# --------------------------------------------------------------------------
class ClaimLedger(object):
    """Exactly-once claims with crash-safe terminal transition states."""

    def __init__(self, store=None):
        self.store = store
        self._claims = {}
        self._retired = {}

    def retire_command(self, command_id, evidence=None):
        if self.store is not None:
            return self.store.retire_command(command_id, evidence=evidence)
        self._retired[command_id] = evidence or {}
        return {"command_id": command_id, "retired": True, "evidence": evidence or {}}

    def is_retired(self, command_id):
        if self.store is not None:
            return self.store.is_retired(command_id)
        return command_id in self._retired

    def _command_from_key(self, key):
        return str(key).split("|", 1)[0]

    def prepare_open(self, key, holder, now, receipt_name=None):
        command_id = self._command_from_key(key)
        if self.is_retired(command_id):
            raise ClaimConflict("command {0} is retired and spent".format(command_id))
        if self.store is None:
            existing = self._claims.get(key)
            if existing:
                if (
                    existing.get("state") == "CLAIM_PREPARED"
                    and existing.get("holder") == holder
                    and existing.get("start_receipt_name") == receipt_name
                ):
                    return dict(existing)
                raise ClaimConflict("claim {0} already exists in state {1}".format(key, existing["state"]))
            record = {
                "key": key,
                "holder": holder,
                "opened_at": float(now),
                "state": "CLAIM_PREPARED",
                "sentinel": None,
                "start_receipt_name": receipt_name,
            }
            self._claims[key] = record
            return dict(record)

        def mutate(state):
            if state["retired_commands"].get(command_id):
                raise ClaimConflict("command {0} is retired and spent".format(command_id))
            existing = state["claims"].get(key)
            if existing:
                if (
                    existing.get("state") == "CLAIM_PREPARED"
                    and existing.get("holder") == holder
                    and existing.get("start_receipt_name") == receipt_name
                ):
                    return dict(existing)
                raise ClaimConflict("claim {0} already exists in state {1}".format(key, existing["state"]))
            record = {
                "key": key,
                "holder": holder,
                "opened_at": float(now),
                "state": "CLAIM_PREPARED",
                "sentinel": None,
                "start_receipt_name": receipt_name,
            }
            state["claims"][key] = record
            return dict(record)

        return self.store.transaction(mutate)

    def mark_open(self, key, drive_id=None, digest=None):
        def apply(record):
            if record.get("state") not in ("CLAIM_PREPARED", "OPEN"):
                raise ClaimConflict("claim {0} is not prepared for opening".format(key))
            record["state"] = "OPEN"
            record["start_drive_id"] = drive_id
            record["start_sha256"] = digest
            return record

        return self._update(key, apply)

    def open(self, key, holder, now):
        """Backward-compatible direct open used by unit tests and legacy data."""
        command_id = self._command_from_key(key)
        if self.is_retired(command_id):
            raise ClaimConflict("command {0} is retired and spent".format(command_id))

        def create(claims):
            existing = claims.get(key)
            if existing is not None:
                raise ClaimConflict(
                    "claim {0} already exists in state {1}".format(key, existing["state"])
                )
            record = {
                "key": key,
                "holder": holder,
                "opened_at": float(now),
                "state": "OPEN",
                "sentinel": None,
            }
            claims[key] = record
            return dict(record)

        if self.store is None:
            return create(self._claims)

        def mutate(state):
            if state["retired_commands"].get(command_id):
                raise ClaimConflict("command {0} is retired and spent".format(command_id))
            return create(state["claims"])

        return self.store.transaction(mutate)

    def prepare_terminal(self, key, sentinel, receipt_name):
        def apply(record):
            current = record.get("state")
            if current == "TERMINAL_PREPARED":
                if record.get("sentinel") == sentinel and record.get("terminal_name") == receipt_name:
                    return record
                raise ClaimConflict("terminal preparation conflicts for {0}".format(key))
            if current != "OPEN":
                raise ClaimConflict("claim {0} is not open".format(key))
            record["state"] = "TERMINAL_PREPARED"
            record["sentinel"] = sentinel
            record["terminal_name"] = receipt_name
            return record

        return self._update(key, apply)

    def mark_terminal_uploaded(self, key, drive_id, digest):
        def apply(record):
            if record.get("state") not in ("TERMINAL_PREPARED", "TERMINAL_UPLOADED"):
                raise ClaimConflict("claim {0} has no prepared terminal".format(key))
            record["state"] = "TERMINAL_UPLOADED"
            record["terminal_drive_id"] = drive_id
            record["terminal_sha256"] = digest
            return record

        return self._update(key, apply)

    def resolve_terminal(self, key):
        def apply(record):
            if record.get("state") == "RESOLVED":
                return record
            if record.get("state") != "TERMINAL_UPLOADED":
                raise ClaimConflict("terminal for {0} is not uploaded and verified".format(key))
            record["state"] = "RESOLVED"
            return record

        return self._update(key, apply)

    def resolve(self, key, sentinel):
        """Backward-compatible direct resolution for legacy tests."""
        def apply(record):
            if record.get("state") != "OPEN":
                raise ClaimConflict("claim {0} is not open".format(key))
            record["state"] = "RESOLVED"
            record["sentinel"] = sentinel
            return record

        return self._update(key, apply)

    def _update(self, key, updater):
        if self.store is None:
            existing = self._claims.get(key)
            if existing is None:
                raise ClaimConflict("cannot update unknown claim {0}".format(key))
            updated = updater(dict(existing))
            self._claims[key] = updated
            return dict(updated)

        def mutate(state):
            existing = state["claims"].get(key)
            if existing is None:
                raise ClaimConflict("cannot update unknown claim {0}".format(key))
            updated = updater(dict(existing))
            state["claims"][key] = updated
            return dict(updated)

        return self.store.transaction(mutate)

    def state(self, key):
        if self.store is None:
            existing = self._claims.get(key)
        else:
            existing = self.store.read()["claims"].get(key)
        return None if existing is None else dict(existing)


# --------------------------------------------------------------------------
# Append-only spool
# --------------------------------------------------------------------------
class AppendOnlySpool(object):
    """Local durability that survives Drive outages and process restarts."""

    def __init__(self, root):
        self.root = root
        os.makedirs(self.root, exist_ok=True)
        self.journal_path = os.path.join(self.root, "spool.jsonl")

    def append(self, record):
        safe = stamp_hold(redact_tree(record))
        line = json.dumps(safe, sort_keys=True, ensure_ascii=True)
        with open(self.journal_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return safe

    def put_record(self, name, payload):
        if not isinstance(payload, (bytes, bytearray)):
            raise SpoolCollision("spool payload must be bytes")
        path = os.path.join(self.root, name)
        try:
            handle = open(path, "xb")
        except FileExistsError as exc:
            raise SpoolCollision(
                "refusing to overwrite spooled record {0}".format(name)
            ) from exc
        with handle:
            handle.write(bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        return {"path": path, "sha256": sha256_hex(payload), "bytes": len(payload)}

    def read_record(self, name):
        path = os.path.join(self.root, name)
        try:
            with open(path, "rb") as handle:
                return handle.read()
        except FileNotFoundError:
            raise SpoolCollision("spooled record {0} does not exist".format(name)) from None

    def verify_record(self, name, payload):
        existing = self.read_record(name)
        if existing != bytes(payload):
            raise SpoolCollision("spooled record {0} has different bytes".format(name))
        return {"path": os.path.join(self.root, name), "sha256": sha256_hex(existing), "bytes": len(existing)}

    def read_journal(self):
        if not os.path.exists(self.journal_path):
            return []
        out = []
        with open(self.journal_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out
