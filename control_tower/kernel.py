"""The control kernel: authority, claims, leases, fencing, and the spool.

The invariants here are the reason the tower exists. Each is enforced by a
guard that raises rather than returns a boolean, so a caller cannot proceed by
ignoring a result. Time is always injected, never read from the clock inside a
guard, so every rule is deterministically testable.
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

    Authority comes from folder membership by pinned ID. The title is read for
    display only and is never consulted for permission -- a file named
    ``00_OWNER_AUTHORIZATION__APPROVED_EXECUTE_NOW`` sitting outside the queue
    has exactly as much authority as an empty file, which is none.
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
    """The exactly-once key.

    Bound to the command identity *and* the exact Drive revision, so a revised
    command is a different unit of work rather than a silent re-run.
    """
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
    """A unit of authorized work. Mutation requires explicit owner activation."""

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


def require_mutation_allowed(envelope):
    """Fail closed unless an activated mutation envelope is presented.

    ``None`` is the common case -- a read-only run -- and it is denied here so
    that forgetting to pass an envelope can never be mistaken for permission.
    """
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
    """Monotonic per-scope sequence. A stale writer is rejected, not merely late."""

    def __init__(self):
        self._highest = {}

    def next_sequence(self, scope):
        nxt = self._highest.get(scope, 0) + 1
        self._highest[scope] = nxt
        return nxt

    def highest(self, scope):
        return self._highest.get(scope, 0)

    def require(self, scope, sequence):
        if not isinstance(sequence, int):
            raise FencingViolation("fencing sequence must be an integer")
        current = self._highest.get(scope, 0)
        if sequence < current:
            raise FencingViolation(
                "stale fencing sequence {0} for scope {1}; current is {2}".format(
                    sequence, scope, current
                )
            )
        if sequence == current and current != 0:
            # Equal is not good enough: a zombie holding the old token would
            # otherwise be indistinguishable from the live writer.
            return sequence
        return sequence

    def require_strictly_current(self, scope, sequence):
        """The write path: only the highest issued token may write."""
        current = self._highest.get(scope, 0)
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
    def __init__(self, lease_id, scope, holder, expires_at, fencing_sequence):
        self.lease_id = lease_id
        self.scope = scope
        self.holder = holder
        self.expires_at = float(expires_at)
        self.fencing_sequence = fencing_sequence
        self.released = False

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
    """One active lease per scope. A second holder loses; it does not queue."""

    def __init__(self, fencing=None):
        self.fencing = fencing or FencingRegistry()
        self._active = {}

    def acquire(self, scope, holder, now, ttl_seconds):
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
            expires_at=float(now) + float(ttl_seconds),
            fencing_sequence=sequence,
        )
        self._active[scope] = lease
        return lease

    def release(self, lease):
        lease.released = True
        if self._active.get(lease.scope) is lease:
            del self._active[lease.scope]
        return lease

    def require_valid(self, lease, now):
        if lease is None:
            raise LeaseExpired("no lease supplied")
        if not lease.is_valid(now):
            raise LeaseExpired(
                "lease {0} expired at {1}; now is {2}".format(
                    lease.lease_id, lease.expires_at, now
                )
            )
        self.fencing.require_strictly_current(lease.scope, lease.fencing_sequence)
        return lease


# --------------------------------------------------------------------------
# Claims
# --------------------------------------------------------------------------
class ClaimLedger(object):
    """Exactly-once claims. An unresolved claim blocks every later claim."""

    def __init__(self):
        self._claims = {}

    def open(self, key, holder, now):
        existing = self._claims.get(key)
        if existing is not None and existing["state"] == "OPEN":
            raise ClaimConflict(
                "claim {0} is unresolved, held by {1} since {2}".format(
                    key, existing["holder"], existing["opened_at"]
                )
            )
        if existing is not None and existing["state"] == "RESOLVED":
            raise ClaimConflict(
                "claim {0} already terminalized with {1}".format(
                    key, existing["sentinel"]
                )
            )
        record = {
            "key": key,
            "holder": holder,
            "opened_at": float(now),
            "state": "OPEN",
            "sentinel": None,
        }
        self._claims[key] = record
        return dict(record)

    def resolve(self, key, sentinel):
        existing = self._claims.get(key)
        if existing is None:
            raise ClaimConflict("cannot resolve unknown claim {0}".format(key))
        if existing["state"] != "OPEN":
            raise ClaimConflict("claim {0} is not open".format(key))
        existing["state"] = "RESOLVED"
        existing["sentinel"] = sentinel
        return dict(existing)

    def state(self, key):
        existing = self._claims.get(key)
        return None if existing is None else dict(existing)


# --------------------------------------------------------------------------
# Append-only spool
# --------------------------------------------------------------------------
class AppendOnlySpool(object):
    """Local durability that survives a Drive outage.

    Records are spooled before any network call. Nothing here ever opens a
    file for truncation, and a discrete record is written with exclusive
    create so a name collision raises instead of silently replacing evidence.
    """

    def __init__(self, root):
        self.root = root
        os.makedirs(self.root, exist_ok=True)
        self.journal_path = os.path.join(self.root, "spool.jsonl")

    def append(self, record):
        """Append one redacted, HOLD-stamped record to the journal."""
        safe = stamp_hold(redact_tree(record))
        line = json.dumps(safe, sort_keys=True, ensure_ascii=True)
        with open(self.journal_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return safe

    def put_record(self, name, payload):
        """Write a discrete record exactly once. Collision is an error."""
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
