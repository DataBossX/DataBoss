"""Durable, process-safe state for claims, leases, fencing and retired commands.

The Control Tower must survive process restarts and concurrent workers without
forgetting authority state.  This module stores one small JSON document behind
an exclusive lock file and replaces it atomically after every transaction.

No third-party dependency is used.  The state file contains control metadata
only; it never contains workbook or client-evidence bytes.
"""

from __future__ import absolute_import

import contextlib
import json
import os
import time

from .constants import ControlTowerError


_STATE_SCHEMA = "databossx.control_tower.durable_state.v1"


def _initial_state():
    return {
        "schema": _STATE_SCHEMA,
        "revision": 0,
        "claims": {},
        "leases": {},
        "fencing": {},
        "retired_commands": {},
    }


class DurableStateError(ControlTowerError):
    """The durable state could not be read, locked or committed safely."""


class DurableStateStore(object):
    """Small JSON state store with exclusive transactions and atomic replace."""

    def __init__(self, root, lock_timeout=10.0, poll_interval=0.02):
        self.root = os.path.abspath(root)
        self.path = os.path.join(self.root, "control_state.json")
        self.lock_path = os.path.join(self.root, "control_state.lock")
        self.lock_timeout = float(lock_timeout)
        self.poll_interval = float(poll_interval)
        os.makedirs(self.root, exist_ok=True)
        if not os.path.exists(self.path):
            with self._locked():
                if not os.path.exists(self.path):
                    self._write_unlocked(_initial_state())

    @contextlib.contextmanager
    def _locked(self):
        deadline = time.monotonic() + self.lock_timeout
        fd = None
        while fd is None:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise DurableStateError(
                        "timed out waiting for durable-state lock {0}".format(self.lock_path)
                    )
                time.sleep(self.poll_interval)
        try:
            os.write(fd, str(os.getpid()).encode("ascii", "strict"))
            os.fsync(fd)
            yield
        finally:
            try:
                os.close(fd)
            finally:
                try:
                    os.unlink(self.lock_path)
                except FileNotFoundError:
                    pass

    def _read_unlocked(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (OSError, ValueError) as exc:
            raise DurableStateError("cannot read durable state: {0}".format(exc)) from None
        if not isinstance(state, dict) or state.get("schema") != _STATE_SCHEMA:
            raise DurableStateError("durable state schema is missing or unsupported")
        for key in ("claims", "leases", "fencing", "retired_commands"):
            if not isinstance(state.get(key), dict):
                raise DurableStateError("durable state field {0} is not a mapping".format(key))
        return state

    def _write_unlocked(self, state):
        state = dict(state)
        state["schema"] = _STATE_SCHEMA
        state["revision"] = int(state.get("revision", 0)) + 1
        temporary = "{0}.{1}.tmp".format(self.path, os.getpid())
        payload = json.dumps(
            state, sort_keys=True, ensure_ascii=True, indent=2, separators=(",", ": ")
        ).encode("utf-8") + b"\n"
        try:
            with open(temporary, "xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            try:
                directory_fd = os.open(self.root, os.O_RDONLY)
            except OSError:
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                except OSError:
                    pass
                finally:
                    os.close(directory_fd)
        except OSError as exc:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise DurableStateError("cannot commit durable state: {0}".format(exc)) from None
        return state

    def read(self):
        with self._locked():
            return self._read_unlocked()

    def transaction(self, mutator):
        """Run ``mutator(state)`` under one lock and atomically persist it.

        The mutator may modify ``state`` in place and return any result.  If it
        raises, no state is written.
        """
        with self._locked():
            state = self._read_unlocked()
            result = mutator(state)
            self._write_unlocked(state)
            return result

    def retire_command(self, command_id, evidence=None):
        if not command_id:
            raise DurableStateError("retired command requires an ID")

        def mutate(state):
            existing = state["retired_commands"].get(command_id)
            record = {
                "command_id": command_id,
                "evidence": evidence or {},
                "retired": True,
            }
            if existing and existing != record:
                raise DurableStateError(
                    "retired command {0} already has conflicting evidence".format(command_id)
                )
            state["retired_commands"][command_id] = record
            return dict(record)

        return self.transaction(mutate)

    def is_retired(self, command_id):
        return bool(self.read()["retired_commands"].get(command_id))

    def reconcile(self, records, retired_command_ids=None):
        """Rebuild safe durable facts from verified append-only records.

        Only explicit identifiers supplied by the caller are retired.  Receipt
        records may restore claim terminal states when they contain a claim key
        and terminal sentinel.  Ambiguous or conflicting records fail closed.
        """
        retired_command_ids = tuple(retired_command_ids or ())

        def mutate(state):
            for command_id in retired_command_ids:
                state["retired_commands"].setdefault(
                    command_id,
                    {"command_id": command_id, "evidence": {"source": "reconcile"}, "retired": True},
                )
            for record in records or ():
                if not isinstance(record, dict):
                    raise DurableStateError("reconciliation record is not a mapping")
                key = record.get("claim_key")
                sentinel = record.get("terminal_sentinel")
                if not key or not sentinel:
                    continue
                existing = state["claims"].get(key)
                rebuilt = {
                    "key": key,
                    "holder": record.get("holder", "reconciled"),
                    "opened_at": record.get("opened_at", 0.0),
                    "state": "RESOLVED",
                    "sentinel": sentinel,
                    "terminal_name": record.get("title") or record.get("name"),
                    "terminal_drive_id": record.get("drive_id"),
                    "terminal_sha256": record.get("sha256"),
                }
                if existing and existing.get("state") == "RESOLVED":
                    if existing.get("sentinel") != sentinel:
                        raise DurableStateError("conflicting terminal sentinels for {0}".format(key))
                    continue
                if existing and existing.get("state") not in (
                    "OPEN",
                    "TERMINAL_PREPARED",
                    "TERMINAL_UPLOADED",
                ):
                    raise DurableStateError("ambiguous claim state for {0}".format(key))
                state["claims"][key] = rebuilt
            return {
                "claims": len(state["claims"]),
                "retired_commands": len(state["retired_commands"]),
            }

        return self.transaction(mutate)
