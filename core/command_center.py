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
    max_age = int(payload.get("max_age_seconds", 86_400))
    if max_age < 1 or max_age > 604_800:
        raise JobValidationError("max_age_seconds must be 1..604800")
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
    MAX_JOB_BYTES = 256 * 1024

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

    def process_next(self) -> Optional[Dict[str, Any]]:
        jobs = sorted(self.folders["inbox"].glob("*.json"))
        if not jobs:
            return None
        source = jobs[0]
        if source.is_symlink():
            destination = self._move(source, "quarantine")
            return {"status": "quarantine", "path": str(destination), "reason": "symlink"}
        try:
            if source.stat().st_size > self.MAX_JOB_BYTES:
                raise JobValidationError("job exceeds maximum size")
            payload = validate_job(json.loads(source.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValueError, SecurityViolation) as exc:
            destination = self._move(source, "rejected")
            receipt = {
                "status": "rejected", "reason": type(exc).__name__,
                "detail": str(exc), "at": utc_now(),
            }
            self._atomic_json(self.folders["receipts"] / f"{source.stem}_REJECTED.json", receipt)
            return receipt | {"path": str(destination)}

        claimed = self._move(source, "claimed")
        job_id = str(payload["job_id"])
        try:
            self.store.submit(payload)
        except DuplicateJob as exc:
            duplicate = self._move(claimed, "quarantine")
            receipt = {"job_id": job_id, "status": "quarantine", "reason": str(exc), "at": utc_now()}
            self._atomic_json(self.folders["receipts"] / f"{job_id}_DUPLICATE.json", receipt)
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
            terminal = self._move(running, "completed")
            self.store.transition(
                job_id, "running", "completed", completed_at=utc_now()
            )
            receipt = {
                "schema_id": "dbx.completion_receipt.v1", "job_id": job_id,
                "operation": payload["operation"], "status": "completed",
                "result": result, "terminal_job_path": str(terminal), "at": utc_now(),
            }
            self._atomic_json(self.folders["receipts"] / f"{job_id}_COMPLETED.json", receipt)
            return receipt
        except Exception as exc:
            terminal = self._move(running, "failed")
            self.store.transition(
                job_id, "running", "failed", completed_at=utc_now(),
                error=type(exc).__name__,
            )
            receipt = {
                "schema_id": "dbx.completion_receipt.v1", "job_id": job_id,
                "status": "failed", "error_type": type(exc).__name__,
                "error": str(exc), "terminal_job_path": str(terminal), "at": utc_now(),
            }
            self._atomic_json(self.folders["receipts"] / f"{job_id}_FAILED.json", receipt)
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
