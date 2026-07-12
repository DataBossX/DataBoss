"""Audited filesystem command center; never executes job-supplied code."""

from __future__ import annotations

import json
import os
import shutil
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .contracts import canonical_hash, utc_now
from .section32 import execute_source_limited_run, sha256_file
from .security import SecurityViolation, redact, resolve_bounded_path, validate_operation
from .state import DuplicateJob, StateStore


class JobValidationError(ValueError):
    pass


def _system_limit(name: str) -> int:
    path = Path(__file__).resolve().parents[1] / "config" / "system.yaml"
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = raw_line.strip().partition(":")
            if separator and key == name:
                parsed = int(value.strip())
                if parsed < 1:
                    raise ValueError
                return parsed
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"invalid system policy value {name!r}") from exc
    raise RuntimeError(f"system policy is missing {name!r}")


SYSTEM_MAX_JOB_BYTES = _system_limit("maximum_job_bytes")
MAX_JOB_AGE_SECONDS = _system_limit("maximum_job_age_seconds")


def validate_job(payload: Any, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise JobValidationError("job must be a JSON object")
    required = {"schema_id", "job_id", "operation", "created_at"}
    missing = sorted(required - payload.keys())
    if missing:
        raise JobValidationError(f"missing required fields: {missing}")
    if payload["schema_id"] != "dbx.command_job.v1":
        raise JobValidationError("unsupported schema_id")
    job_id = str(payload["job_id"])
    if not job_id or len(job_id) > 128 or not all(
        character.isalnum() or character in "-_" for character in job_id
    ):
        raise JobValidationError("job_id contains prohibited characters")
    validate_operation(str(payload["operation"]))
    try:
        created = datetime.fromisoformat(str(payload["created_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise JobValidationError("created_at must be ISO-8601") from exc
    if created.tzinfo is None:
        raise JobValidationError("created_at must include a timezone")
    current = now or datetime.now(timezone.utc)
    if created.astimezone(timezone.utc) - current > timedelta(minutes=5):
        raise JobValidationError("created_at is beyond permitted clock skew")
    max_age = int(payload.get("max_age_seconds", MAX_JOB_AGE_SECONDS))
    if max_age < 1 or max_age > MAX_JOB_AGE_SECONDS:
        raise JobValidationError(
            f"max_age_seconds must be 1..{MAX_JOB_AGE_SECONDS}"
        )
    if current - created.astimezone(timezone.utc) > timedelta(seconds=max_age):
        raise JobValidationError("job is expired")
    timeout = int(payload.get("timeout_seconds", 300))
    if timeout < 1 or timeout > 86_400:
        raise JobValidationError("timeout_seconds must be 1..86400")
    if "content_sha256" in payload:
        hashable = {key: value for key, value in payload.items() if key != "content_sha256"}
        if canonical_hash(hashable) != payload["content_sha256"]:
            raise JobValidationError("content_sha256 mismatch")
    return payload


class CommandCenter:
    MAX_JOB_BYTES = SYSTEM_MAX_JOB_BYTES

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.folders = {
            name: self.root / name
            for name in (
                "inbox", "claimed", "running", "completed", "failed",
                "rejected", "quarantine", "receipts", "heartbeats", "outputs",
            )
        }
        for folder in self.folders.values():
            folder.mkdir(exist_ok=True)
        self.store = StateStore(self.root / "command_center.sqlite3")
        self.lock_path = self.root / ".watcher.lock"
        self._recover_interrupted_jobs()

    def close(self) -> None:
        self.store.close()

    @contextmanager
    def single_instance(self) -> Iterator[None]:
        try:
            descriptor = os.open(
                self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
        except FileExistsError as exc:
            raise RuntimeError("another command-center watcher holds the lock") from exc
        try:
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.close(descriptor)
            yield
        finally:
            self.lock_path.unlink(missing_ok=True)

    def _atomic_json(self, path: Path, payload: Dict[str, Any]) -> None:
        safe = redact(payload)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(safe, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(path)

    def _move(self, source: Path, destination_folder: str) -> Path:
        destination = self.folders[destination_folder] / source.name
        source.replace(destination)
        return destination

    def _recover_interrupted_jobs(self) -> None:
        """Fail closed or finish filesystem moves left by a prior crash."""
        for path in sorted(self.folders["claimed"].glob("*.json")):
            row = self.store.connection.execute(
                "SELECT state FROM jobs WHERE job_id=?", (path.stem,)
            ).fetchone()
            if row is None:
                path.replace(self.folders["inbox"] / path.name)
            elif row["state"] == "claimed":
                self.store.transition(
                    path.stem,
                    "claimed",
                    "failed",
                    completed_at=utc_now(),
                    error="InterruptedBeforeExecution",
                )
                path.replace(self.folders["failed"] / path.name)
        for path in sorted(self.folders["running"].glob("*.json")):
            row = self.store.connection.execute(
                "SELECT state FROM jobs WHERE job_id=?", (path.stem,)
            ).fetchone()
            if row is None:
                path.replace(self.folders["quarantine"] / path.name)
            elif row["state"] == "running":
                self.store.transition(
                    path.stem,
                    "running",
                    "failed",
                    completed_at=utc_now(),
                    error="InterruptedDuringExecution",
                )
                path.replace(self.folders["failed"] / path.name)
            elif row["state"] == "completed":
                path.replace(self.folders["completed"] / path.name)

    def process_next(self) -> Optional[Dict[str, Any]]:
        jobs = sorted(self.folders["inbox"].glob("*.json"))
        if not jobs:
            return None
        source = jobs[0]
        claimed = self._move(source, "claimed")
        try:
            if claimed.is_symlink():
                raise SecurityViolation("symlink jobs are prohibited")
            if claimed.stat().st_size > self.MAX_JOB_BYTES:
                raise JobValidationError("job exceeds maximum size")
            before = claimed.stat()
            payload = validate_job(json.loads(claimed.read_text(encoding="utf-8")))
            if claimed.stem != str(payload["job_id"]):
                raise JobValidationError("job filename must equal job_id plus .json")
            after = claimed.stat()
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_ino, after.st_size, after.st_mtime_ns
            ):
                raise SecurityViolation("claimed job changed during validation")
            claimed_sha256 = sha256_file(claimed)
        except (OSError, json.JSONDecodeError, ValueError, SecurityViolation) as exc:
            destination = self._move(claimed, "rejected")
            receipt = {
                "status": "rejected",
                "reason": type(exc).__name__,
                "detail": str(exc),
                "at": utc_now(),
            }
            self._atomic_json(
                self.folders["receipts"] / f"{claimed.stem}_REJECTED.json",
                receipt,
            )
            return receipt | {"path": str(destination)}

        job_id = str(payload["job_id"])
        try:
            self.store.submit(payload)
        except DuplicateJob as exc:
            duplicate = self._move(claimed, "quarantine")
            receipt = {
                "job_id": job_id,
                "status": "quarantine",
                "reason": str(exc),
                "at": utc_now(),
            }
            self._atomic_json(
                self.folders["receipts"] / f"{job_id}_DUPLICATE.json",
                receipt,
            )
            return receipt | {"path": str(duplicate)}

        now = utc_now()
        self.store.transition(job_id, "inbox", "claimed", claimed_at=now)
        ack = {
            "schema_id": "dbx.ack_receipt.v1", "job_id": job_id,
            "operation": payload["operation"], "status": "claimed", "at": now,
        }
        self._atomic_json(self.folders["receipts"] / f"{job_id}_ACK.json", ack)
        running = self._move(claimed, "running")
        self.store.transition(job_id, "claimed", "running", heartbeat_at=utc_now())
        self.store.heartbeat(job_id)
        self._atomic_json(
            self.folders["heartbeats"] / f"{job_id}.json",
            {"job_id": job_id, "state": "running", "at": utc_now()},
        )

        try:
            result = self._execute(payload)
            if running.is_symlink() or sha256_file(running) != claimed_sha256:
                raise SecurityViolation("claimed job changed after validation")
        except Exception as exc:
            terminal = self.folders["failed"] / running.name
            receipt = {
                "schema_id": "dbx.command_completion_receipt.v1", "job_id": job_id,
                "status": "failed", "error_type": type(exc).__name__,
                "error": str(exc), "terminal_job_path": str(terminal), "at": utc_now(),
            }
            self._atomic_json(self.folders["receipts"] / f"{job_id}_FAILED.json", receipt)
            self.store.transition(
                job_id, "running", "failed", completed_at=utc_now(),
                error=type(exc).__name__,
            )
            self._move(running, "failed")
            return receipt

        terminal = self.folders["completed"] / running.name
        receipt = {
            "schema_id": "dbx.command_completion_receipt.v1", "job_id": job_id,
            "operation": payload["operation"], "status": "completed",
            "result": result, "terminal_job_path": str(terminal), "at": utc_now(),
        }
        self._atomic_json(self.folders["receipts"] / f"{job_id}_COMPLETED.json", receipt)
        self.store.transition(
            job_id, "running", "completed", completed_at=utc_now()
        )
        self._move(running, "completed")
        return receipt

    def _execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        operation = validate_operation(str(payload["operation"]))
        if operation == "communication_loop_self_test":
            return {"mode": "safe_no_op", "proof": canonical_hash(payload)}
        if operation == "run_section32_evidence_audit":
            run_dir = execute_source_limited_run(self.folders["outputs"])
            return {
                "run_directory": str(run_dir),
                "completion_receipt_sha256": sha256_file(run_dir / "COMPLETION_RECEIPT.json"),
                "release_state": "HOLD_NO_RELEASE",
            }
        if operation in {"inventory_artifacts_read_only", "verify_hashes_read_only"}:
            requested = payload.get("parameters", {}).get("path", str(self.root))
            root = resolve_bounded_path(Path(requested), [self.root], must_exist=True)
            files = [
                {
                    "path": str(path.relative_to(root)),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in sorted(root.rglob("*"))
                if path.is_file() and not path.is_symlink()
            ]
            return {"root": str(root), "files": files}
        raise JobValidationError(
            f"operation {operation!r} is approved but requires an explicit project work order"
        )
