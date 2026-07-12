"""Fail-closed, local-only watcher for a synchronized Drive command center.

Only built-in no-op jobs are supported.  This module never executes job text,
shell commands, dynamic Python, or paths outside the configured command center.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import errno
import hashlib
import json
import os
import re
import signal
import socket
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

VERSION = "1.0.0"
EXPECTED_FOLDERS = (
    "inbox",
    "claimed",
    "running",
    "completed",
    "failed",
    "rejected",
    "results",
    "logs",
    "quarantine",
    "schemas",
    "config",
)
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}\.json$")
SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
TRANSIENT_ERRORS = (OSError, TimeoutError)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_move_no_replace(source: Path, destination: Path) -> None:
    """Atomically move without replacing an existing destination."""
    if os.name == "nt":
        os.rename(source, destination)
        return
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
        renameat2.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        renameat2.restype = ctypes.c_int
        result = renameat2(
            -100,
            os.fsencode(source),
            -100,
            os.fsencode(destination),
            1,
        )
        if result == 0:
            return
        error_number = ctypes.get_errno()
        raise OSError(
            error_number,
            os.strerror(error_number),
            str(destination),
        )
    try:
        os.link(source, destination, follow_symlinks=False)
    except TypeError:
        os.link(source, destination)
    try:
        source.unlink()
    except OSError:
        with contextlib.suppress(OSError):
            destination.unlink()
        raise


def atomic_write_json(
    path: Path,
    value: dict[str, Any],
    *,
    allow_replace: bool = True,
    max_retries: int = 5,
) -> None:
    for attempt in range(max_retries):
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{attempt}.tmp")
        temporary_created = False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("x", encoding="utf-8", newline="\n") as output:
                temporary_created = True
                json.dump(value, output, indent=2, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            if allow_replace:
                os.replace(temporary, path)
            else:
                os.link(temporary, path)
            return
        except FileExistsError:
            raise
        except TRANSIENT_ERRORS:
            if attempt + 1 == max_retries:
                raise
            time.sleep(min(2**attempt, 16))
        finally:
            if temporary_created:
                with contextlib.suppress(FileNotFoundError):
                    temporary.unlink()


@dataclass(frozen=True)
class WatcherConfig:
    root: Path
    canonical_folder_id: str
    local_state_dir: Path | None = None
    poll_interval_seconds: int = 60
    heartbeat_interval_seconds: int = 240
    claim_ack_deadline_seconds: int = 120
    stale_job_seconds: int = 900
    max_file_bytes: int = 1_048_576
    max_retries: int = 5
    supported_schema_versions: tuple[str, ...] = ("1.0",)
    allowed_operations: tuple[str, ...] = ("noop",)
    expected_folders: tuple[str, ...] = EXPECTED_FOLDERS

    @classmethod
    def from_file(cls, path: Path) -> "WatcherConfig":
        with path.open(encoding="utf-8") as source:
            raw = json.load(source)
        root_text = os.path.expandvars(str(raw.get("root", ""))).strip()
        folder_id = str(raw.get("canonical_folder_id", "")).strip()
        if not root_text or not folder_id:
            raise ValueError("root and canonical_folder_id are required")
        root = Path(root_text).expanduser().resolve()
        state_text = os.path.expandvars(str(raw.get("local_state_dir", ""))).strip()
        return cls(
            root=root,
            canonical_folder_id=folder_id,
            local_state_dir=Path(state_text).expanduser().resolve() if state_text else None,
            poll_interval_seconds=int(raw.get("poll_interval_seconds", 60)),
            heartbeat_interval_seconds=int(raw.get("heartbeat_interval_seconds", 240)),
            claim_ack_deadline_seconds=int(raw.get("claim_ack_deadline_seconds", 120)),
            stale_job_seconds=int(raw.get("stale_job_seconds", 900)),
            max_file_bytes=int(raw.get("max_file_bytes", 1_048_576)),
            max_retries=int(raw.get("max_retries", 5)),
            supported_schema_versions=tuple(raw.get("supported_schema_versions", ["1.0"])),
            allowed_operations=tuple(raw.get("allowed_operations", ["noop"])),
        )

    def validate(self) -> None:
        if self.poll_interval_seconds != 60:
            raise ValueError("poll_interval_seconds must be 60")
        if not 1 <= self.heartbeat_interval_seconds <= 300:
            raise ValueError("heartbeat interval must be between 1 and 300 seconds")
        if not 1 <= self.claim_ack_deadline_seconds <= 120:
            raise ValueError("acknowledgment deadline must be between 1 and 120 seconds")
        if not 1 <= self.max_retries <= 10:
            raise ValueError("max_retries must be between 1 and 10")
        if self.max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive")
        if set(self.allowed_operations) - {"noop"}:
            raise ValueError("only the built-in noop operation is supported")
        if self.local_state_dir is not None:
            try:
                self.local_state_dir.relative_to(self.root)
            except ValueError:
                pass
            else:
                raise ValueError("local_state_dir must be outside the synchronized root")


@dataclass
class JobRecord:
    path: Path
    job_id: str
    input_name: str
    input_hash: str
    ack_delay_seconds: float = 0.0
    created_files: list[str] = field(default_factory=list)
    moved_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SingleInstanceLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._owned = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                pid = int(self.path.read_text(encoding="ascii").strip())
            except (OSError, ValueError):
                pid = -1
            if pid > 0 and self._pid_exists(pid):
                raise RuntimeError(f"watcher already running with PID {pid}")
            stale = self.path.with_suffix(f".stale.{int(time.time())}")
            os.replace(self.path, stale)
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as output:
            output.write(str(os.getpid()))
            output.flush()
            os.fsync(output.fileno())
        self._owned = True

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        if os.name == "nt":
            import ctypes

            process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if process:
                ctypes.windll.kernel32.CloseHandle(process)
                return True
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def release(self) -> None:
        if self._owned:
            with contextlib.suppress(FileNotFoundError):
                self.path.unlink()
            self._owned = False

    def __enter__(self) -> "SingleInstanceLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


class CommandCenterWatcher:
    def __init__(self, config: WatcherConfig) -> None:
        config.validate()
        self.config = config
        self.root = config.root
        self.stop_requested = False
        self.last_successful_poll = ""
        self.last_error = ""
        self.hostname = socket.gethostname()
        self.pid = os.getpid()
        self.lock = SingleInstanceLock(self.root / "config" / "watcher.lock")

    def relative(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.root))

    def path(self, folder: str, name: str = "") -> Path:
        if folder not in self.config.expected_folders:
            raise ValueError(f"path outside allowlist: {folder}")
        candidate = (self.root / folder / name).resolve()
        candidate.relative_to(self.root)
        return candidate

    def validate_layout(self) -> list[str]:
        if not self.root.is_dir():
            raise FileNotFoundError(f"command center unavailable: {self.root}")
        missing = [name for name in self.config.expected_folders if not self.path(name).is_dir()]
        if missing:
            raise FileNotFoundError(f"missing expected folders: {', '.join(missing)}")
        return list(self.config.expected_folders)

    def log(self, event: str, **fields: Any) -> None:
        record = {
            "timestamp_utc": iso_utc(),
            "event": event,
            "watcher_version": VERSION,
            "pid": self.pid,
            **fields,
        }
        log_path = self.path("logs", f"watcher-{utc_now():%Y-%m-%d}.jsonl")
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        for attempt in range(self.config.max_retries):
            try:
                with log_path.open("a", encoding="utf-8", newline="\n") as output:
                    output.write(line)
                    output.flush()
                return
            except TRANSIENT_ERRORS:
                if attempt + 1 == self.config.max_retries:
                    raise
                time.sleep(min(2**attempt, 16))

    def online_payload(self, status: str) -> dict[str, Any]:
        now = utc_now()
        return {
            "current_utc": iso_utc(now),
            "local_central": now.astimezone(ZoneInfo("America/Chicago")).isoformat(),
            "hostname": self.hostname,
            "process_id": self.pid,
            "watcher_version": VERSION,
            "canonical_folder_id": self.config.canonical_folder_id,
            "detected_local_sync_path": str(self.root),
            "poll_interval_seconds": self.config.poll_interval_seconds,
            "last_successful_poll": self.last_successful_poll or None,
            "current_status": status,
            "last_error": self.last_error or None,
            "supported_schema_versions": list(self.config.supported_schema_versions),
        }

    def refresh_online(self, status: str) -> None:
        atomic_write_json(
            self.root / "WATCHER_ONLINE.json",
            self.online_payload(status),
            max_retries=self.config.max_retries,
        )

    def base_receipt(
        self,
        record: JobRecord,
        status: str,
        errors: Iterable[str] = (),
        completed: bool = False,
    ) -> dict[str, Any]:
        receipt: dict[str, Any] = {
            "schema_version": "1.0",
            "job_id": record.job_id,
            "status": status,
            "created_utc": iso_utc(),
            "hostname": self.hostname,
            "watcher_version": VERSION,
            "watcher_pid": self.pid,
            "canonical_folder_id": self.config.canonical_folder_id,
            "local_sync_path": str(self.root),
            "input_filename": record.input_name,
            "input_sha256": record.input_hash,
            "files_created": record.created_files,
            "files_moved": record.moved_files,
            "files_modified": record.modified_files,
            "errors": list(errors),
            "warnings": record.warnings,
            "next_recommended_action": "none" if not errors else "review errors and retry with a new job ID",
            "safety_statement": "Original project evidence and Dropbox were not modified.",
        }
        if completed:
            receipt["completed_utc"] = iso_utc()
        return receipt

    def _move(self, source: Path, destination: Path, record: JobRecord | None = None) -> None:
        if source.parent.name not in self.config.expected_folders:
            raise ValueError("source path is outside the command center allowlist")
        if destination.parent.name not in self.config.expected_folders:
            raise ValueError("destination path is outside the command center allowlist")
        for attempt in range(self.config.max_retries):
            try:
                atomic_move_no_replace(source, destination)
                break
            except OSError as error:
                if error.errno in (errno.EEXIST, errno.ENOTEMPTY):
                    raise FileExistsError(
                        f"refusing to overwrite existing state file: {destination.name}"
                    ) from error
                if attempt + 1 == self.config.max_retries:
                    raise
                time.sleep(min(2**attempt, 16))
        if record:
            record.moved_files.append(f"{self.relative(source)} -> {self.relative(destination)}")

    def _reject_unreadable(self, source: Path, reason: str, quarantine: bool) -> None:
        destination_folder = "quarantine" if quarantine else "rejected"
        destination = self.path(destination_folder, source.name)
        if destination.exists():
            destination = self.path(
                destination_folder, f"{source.stem}.{int(time.time())}{source.suffix}"
            )
        self._move(source, destination)
        self.log("job_rejected", input_filename=source.name, destination=destination_folder, reason=reason)

    def _known_jobs(self) -> tuple[set[str], set[str]]:
        ids: set[str] = set()
        hashes: set[str] = set()
        for folder in ("claimed", "running", "completed", "failed", "quarantine"):
            for path in self.path(folder).glob("*.json"):
                try:
                    with path.open(encoding="utf-8") as source:
                        value = json.load(source)
                    job_id = value.get("job_id")
                    input_hash = value.get("input_sha256")
                    if isinstance(job_id, str):
                        ids.add(job_id)
                    if isinstance(input_hash, str):
                        hashes.add(input_hash)
                except (OSError, ValueError, TypeError):
                    continue
        return ids, hashes

    def claim(self, source: Path) -> JobRecord | None:
        claim_started = time.monotonic()
        if source.is_symlink():
            self._reject_unreadable(source, "symbolic links are not allowed", quarantine=True)
            return None
        if not SAFE_NAME.fullmatch(source.name):
            self._reject_unreadable(source, "unsafe filename", quarantine=True)
            return None
        try:
            size = source.stat().st_size
        except OSError as error:
            self.log("claim_deferred", input_filename=source.name, error=type(error).__name__)
            return None
        if size > self.config.max_file_bytes:
            self._reject_unreadable(source, "file exceeds size limit", quarantine=True)
            return None
        job: Any = None
        input_hash = ""
        for attempt in range(self.config.max_retries):
            try:
                input_hash = sha256_file(source)
                with source.open(encoding="utf-8") as input_file:
                    job = json.load(input_file)
                break
            except OSError:
                if attempt + 1 == self.config.max_retries:
                    self._reject_unreadable(
                        source,
                        "temporary sync failure exceeded maximum retries",
                        quarantine=True,
                    )
                    return None
                time.sleep(min(2**attempt, 16))
            except (UnicodeError, json.JSONDecodeError):
                break
        if job is None:
            self._reject_unreadable(source, "malformed JSON", quarantine=True)
            return None
        errors = self.validate_job(job)
        if errors:
            self._reject_unreadable(source, "; ".join(errors), quarantine=False)
            return None
        job_id = job["job_id"]
        if source.name != f"JOB_{job_id}.json":
            self._reject_unreadable(
                source, "filename does not match the declared job ID", quarantine=True
            )
            return None
        known_ids, known_hashes = self._known_jobs()
        if job_id in known_ids or input_hash in known_hashes:
            self._reject_unreadable(source, "duplicate job ID or content hash", quarantine=True)
            return None
        claimed = self.path("claimed", source.name)
        if claimed.exists():
            self._reject_unreadable(source, "claimed destination already exists", quarantine=True)
            return None
        record = JobRecord(source, job_id, source.name, input_hash)
        self._move(source, claimed, record)
        record.path = claimed
        try:
            if sha256_file(claimed) != input_hash:
                quarantine = self.path(
                    "quarantine", f"CHANGED_DURING_CLAIM_{claimed.name}"
                )
                self._move(claimed, quarantine, record)
                self.log(
                    "job_quarantined",
                    job_id=job_id,
                    reason="content changed during claim",
                )
                return None
            ack = self.path("results", f"ACK_{job_id}.json")
            record.created_files.append(self.relative(ack))
            atomic_write_json(
                ack,
                self.base_receipt(record, "claimed"),
                allow_replace=False,
                max_retries=self.config.max_retries,
            )
        except Exception as error:
            record.created_files[:] = [
                name for name in record.created_files if (self.root / name).exists()
            ]
            self.fail(record, error)
            return None
        record.ack_delay_seconds = time.monotonic() - claim_started
        self.log("job_claimed", job_id=job_id, input_sha256=input_hash)
        return record

    def validate_job(self, job: Any) -> list[str]:
        if not isinstance(job, dict):
            return ["job must be a JSON object"]
        required = {"schema_version", "job_id", "operation"}
        errors = [f"missing {name}" for name in sorted(required - set(job))]
        if str(job.get("schema_version")) not in self.config.supported_schema_versions:
            errors.append("unsupported schema_version")
        if not isinstance(job.get("job_id"), str) or not SAFE_JOB_ID.fullmatch(job.get("job_id", "")):
            errors.append("invalid job_id")
        if job.get("operation") not in self.config.allowed_operations:
            errors.append("operation is not allowlisted")
        description = job.get("description")
        if description is not None and (
            not isinstance(description, str) or len(description) > 500
        ):
            errors.append("description must be a string no longer than 500 characters")
        created = job.get("created_utc")
        if created is not None:
            if not isinstance(created, str):
                errors.append("created_utc must be an ISO-8601 string")
            else:
                try:
                    parsed = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        raise ValueError
                except ValueError:
                    errors.append("created_utc must include a valid timezone")
        if set(job) - {"schema_version", "job_id", "operation", "description", "created_utc"}:
            errors.append("unrecognized job fields")
        return errors

    def execute(self, record: JobRecord) -> None:
        if record.ack_delay_seconds > self.config.claim_ack_deadline_seconds:
            raise TimeoutError(
                f"acknowledgment exceeded {self.config.claim_ack_deadline_seconds}-second deadline"
            )
        running = self.path("running", record.path.name)
        self._move(record.path, running, record)
        record.path = running
        heartbeat = self.path("logs", f"HEARTBEAT_{record.job_id}.json")
        record.created_files.append(self.relative(heartbeat))
        atomic_write_json(
            heartbeat,
            {
                **self.base_receipt(record, "running"),
                "heartbeat_utc": iso_utc(),
                "expected_folders_detected": list(self.config.expected_folders),
            },
            max_retries=self.config.max_retries,
        )
        receipt_path = self.path("completed", f"RESULT_{record.job_id}.json")
        record.created_files.append(self.relative(receipt_path))
        archived_job = self.path("completed", record.path.name)
        self._move(record.path, archived_job, record)
        record.path = archived_job
        receipt = self.base_receipt(record, "completed", completed=True)
        receipt["expected_folders_detected"] = list(self.config.expected_folders)
        receipt["source_files_modified"] = False
        atomic_write_json(
            receipt_path,
            receipt,
            allow_replace=False,
            max_retries=self.config.max_retries,
        )
        try:
            self.write_local_proof(record, receipt_path)
        except Exception:
            self._quarantine_conflict(receipt_path)
            raise
        self.log("job_completed", job_id=record.job_id, receipt=self.relative(receipt_path))

    def fail(self, record: JobRecord, error: Exception) -> None:
        message = f"{type(error).__name__}: {error}"
        receipt_path = self.path("failed", f"RESULT_{record.job_id}.json")
        if receipt_path.exists():
            self._quarantine_conflict(receipt_path)
        if record.path.exists():
            failed_job = self.path("failed", record.path.name)
            if failed_job != record.path and failed_job.exists():
                self._quarantine_conflict(failed_job)
            self._move(record.path, failed_job, record)
            record.path = failed_job
        record.created_files.append(self.relative(receipt_path))
        atomic_write_json(
            receipt_path,
            self.base_receipt(record, "failed", [message], completed=True),
            allow_replace=False,
            max_retries=self.config.max_retries,
        )
        self.log("job_failed", job_id=record.job_id, error=message)

    def _quarantine_conflict(self, path: Path) -> None:
        for counter in range(1_000):
            destination = self.path(
                "quarantine",
                f"CONFLICT_{int(time.time())}_{counter}_{path.name}",
            )
            if destination.exists():
                continue
            self._move(path, destination)
            self.log(
                "conflicting_artifact_quarantined",
                input_filename=path.name,
                destination=self.relative(destination),
            )
            return
        raise RuntimeError(f"unable to allocate quarantine path for {path.name}")

    def write_local_proof(self, record: JobRecord, receipt_path: Path) -> None:
        if self.config.local_state_dir is None:
            return
        proof_path = (
            self.config.local_state_dir
            / "proofs"
            / f"SELFTEST_PROOF_{record.job_id}.json"
        )
        atomic_write_json(
            proof_path,
            {
                "created_utc": iso_utc(),
                "job_id": record.job_id,
                "canonical_folder_id": self.config.canonical_folder_id,
                "local_sync_path": str(self.root),
                "watcher_version": VERSION,
                "watcher_pid": self.pid,
                "input_sha256": record.input_hash,
                "receipt_sha256": sha256_file(receipt_path),
            },
            allow_replace=False,
            max_retries=self.config.max_retries,
        )

    def recover_stale(self) -> None:
        cutoff = time.time() - self.config.stale_job_seconds
        for folder in ("claimed", "running"):
            for path in self.path(folder).glob("*.json"):
                try:
                    stale = path.stat().st_mtime < cutoff
                except OSError:
                    continue
                if not stale:
                    continue
                try:
                    input_hash = sha256_file(path)
                    with path.open(encoding="utf-8") as source:
                        job = json.load(source)
                    errors = self.validate_job(job)
                except (OSError, UnicodeError, json.JSONDecodeError):
                    errors = ["stale state file is unreadable"]
                    job = {}
                    input_hash = ""
                if errors:
                    destination = self.path(
                        "quarantine", f"STALE_{folder}_{path.name}"
                    )
                    if destination.exists():
                        destination = self.path(
                            "quarantine",
                            f"STALE_{folder}_{int(time.time())}_{path.name}",
                        )
                    self._move(path, destination)
                    self.log(
                        "stale_job_quarantined",
                        input_filename=path.name,
                        previous_state=folder,
                        destination=self.relative(destination),
                        reason="; ".join(errors),
                    )
                    continue
                record = JobRecord(
                    path=path,
                    job_id=job["job_id"],
                    input_name=path.name,
                    input_hash=input_hash,
                )
                self.fail(
                    record,
                    RuntimeError(
                        f"crash recovery terminated stale {folder} job"
                    ),
                )

    def poll_once(self) -> int:
        self.validate_layout()
        self.recover_stale()
        processed = 0
        for source in sorted(self.path("inbox").glob("*")):
            if not source.is_file():
                continue
            record = self.claim(source)
            if record is None:
                continue
            try:
                self.execute(record)
            except Exception as error:
                self.fail(record, error)
            processed += 1
        self.last_successful_poll = iso_utc()
        self.last_error = ""
        self.refresh_online("online")
        self.log("poll_completed", jobs_processed=processed)
        return processed

    def run(self, once: bool = False) -> int:
        def request_stop(_signum: int, _frame: object) -> None:
            self.stop_requested = True

        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, request_stop)
        failed_poll = False
        with self.lock:
            self.validate_layout()
            self.refresh_online("starting")
            self.log("watcher_started", root=str(self.root))
            while not self.stop_requested:
                try:
                    self.poll_once()
                except Exception as error:
                    failed_poll = True
                    self.last_error = f"{type(error).__name__}: {error}"
                    self.log("poll_failed", error=self.last_error)
                    self.refresh_online("degraded")
                if once:
                    break
                deadline = time.monotonic() + self.config.poll_interval_seconds
                while not self.stop_requested and time.monotonic() < deadline:
                    time.sleep(min(1, deadline - time.monotonic()))
            self.refresh_online("stopped")
            self.log("watcher_stopped")
        return 1 if failed_poll else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--once", action="store_true", help="poll once and exit")
    arguments = parser.parse_args(argv)
    try:
        watcher = CommandCenterWatcher(WatcherConfig.from_file(arguments.config))
        return watcher.run(once=arguments.once)
    except Exception as error:
        print(f"watcher failed closed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
