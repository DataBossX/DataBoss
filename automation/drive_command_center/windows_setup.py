"""Windows detection and least-privileged startup setup for the watcher.

The detector only reads command-center control artifacts. It does not inspect
project evidence or Dropbox and will not guess when the Drive path is ambiguous.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automation.drive_command_center.watcher import (
    EXPECTED_FOLDERS,
    VERSION,
    atomic_write_json,
    sha256_file,
)

CONTROL_FILES = ("watcher_config.json", "WATCHER_ONLINE.json")
SKIP_NAMES = {
    "$recycle.bin",
    "appdata",
    "dropbox",
    "node_modules",
    ".git",
    "windows",
    "program files",
    "program files (x86)",
}


def artifact_folder_id(path: Path) -> str | None:
    for name in CONTROL_FILES:
        artifact = path / name
        try:
            with artifact.open(encoding="utf-8") as source:
                value = json.load(source)
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(value, dict):
            folder_id = value.get("canonical_folder_id")
            if isinstance(folder_id, str) and folder_id:
                return folder_id
    return None


def valid_command_center(path: Path, folder_id: str) -> bool:
    return (
        path.is_dir()
        and all((path / name).is_dir() for name in EXPECTED_FOLDERS)
        and artifact_folder_id(path) == folder_id
    )


def search_roots() -> list[Path]:
    roots: list[Path] = []
    explicit = os.environ.get("DATABOSSX_COMMAND_CENTER")
    if explicit:
        roots.append(Path(explicit).expanduser())
    for drive_letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{drive_letter}:\\")
        if drive.exists():
            roots.append(drive)
    for raw in (os.environ.get("USERPROFILE", ""),):
        if raw:
            candidate = Path(raw)
            if candidate.exists() and candidate not in roots:
                roots.append(candidate)
    return roots


def detect(folder_id: str, max_directories: int = 200_000) -> list[Path]:
    matches: set[Path] = set()
    inspected = 0
    for root in search_roots():
        if valid_command_center(root, folder_id):
            matches.add(root.resolve())
            continue
        for current, directories, files in os.walk(root, topdown=True):
            directories[:] = [
                name
                for name in directories
                if name.lower() not in SKIP_NAMES and not name.startswith(".")
            ]
            inspected += 1
            if inspected > max_directories:
                raise RuntimeError("detection limit reached; set DATABOSSX_COMMAND_CENTER explicitly")
            if set(CONTROL_FILES).intersection(files):
                candidate = Path(current)
                if valid_command_center(candidate, folder_id):
                    matches.add(candidate.resolve())
                    directories[:] = []
    return sorted(matches)


def backup_file(path: Path, backup_directory: Path) -> Path | None:
    if not path.exists():
        return None
    backup_directory.mkdir(parents=True, exist_ok=True)
    destination = backup_directory / path.name
    counter = 1
    while destination.exists():
        destination = backup_directory / f"{path.stem}.{counter}{path.suffix}"
        counter += 1
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copy2(path, temporary)
    os.replace(temporary, destination)
    return destination


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    return value


def successful_self_test(
    root: Path,
    job_id: str,
    canonical_folder_id: str,
    local_state_dir: Path,
) -> bool:
    receipt_path = root / "completed" / f"RESULT_{job_id}.json"
    job_path = root / "completed" / f"JOB_{job_id}.json"
    ack_path = root / "results" / f"ACK_{job_id}.json"
    heartbeat_path = root / "logs" / f"HEARTBEAT_{job_id}.json"
    proof_path = local_state_dir / "proofs" / f"SELFTEST_PROOF_{job_id}.json"
    try:
        receipt = read_json(receipt_path)
        job = read_json(job_path)
        ack = read_json(ack_path)
        heartbeat = read_json(heartbeat_path)
        proof = read_json(proof_path)
        input_hash = sha256_file(job_path)
        receipt_hash = sha256_file(receipt_path)
    except (OSError, ValueError, TypeError):
        return False
    shared_proof = (ack, heartbeat, receipt)
    return (
        job.get("job_id") == job_id
        and job.get("operation") == "noop"
        and ack.get("status") == "claimed"
        and heartbeat.get("status") == "running"
        and receipt.get("status") == "completed"
        and receipt.get("completed_utc")
        and receipt.get("source_files_modified") is False
        and receipt.get("errors") == []
        and receipt.get("expected_folders_detected") == list(EXPECTED_FOLDERS)
        and receipt.get("safety_statement")
        == "Original project evidence and Dropbox were not modified."
        and all(item.get("schema_version") == "1.0" for item in shared_proof)
        and all(item.get("job_id") == job_id for item in shared_proof)
        and all(item.get("input_filename") == job_path.name for item in shared_proof)
        and all(item.get("input_sha256") == input_hash for item in shared_proof)
        and all(
            item.get("canonical_folder_id") == canonical_folder_id
            for item in shared_proof
        )
        and all(Path(item.get("local_sync_path", "")).resolve() == root for item in shared_proof)
        and all(item.get("watcher_version") == VERSION for item in shared_proof)
        and all(isinstance(item.get("watcher_pid"), int) for item in shared_proof)
        and proof.get("job_id") == job_id
        and proof.get("canonical_folder_id") == canonical_folder_id
        and Path(proof.get("local_sync_path", "")).resolve() == root
        and proof.get("watcher_version") == VERSION
        and proof.get("input_sha256") == input_hash
        and proof.get("receipt_sha256") == receipt_hash
    )


def install_startup(config_path: Path, self_test_job_id: str) -> Path:
    with config_path.open(encoding="utf-8") as source:
        config = json.load(source)
    root = Path(os.path.expandvars(config["root"])).expanduser().resolve()
    canonical_folder_id = str(config["canonical_folder_id"])
    state_text = os.path.expandvars(str(config.get("local_state_dir", ""))).strip()
    if not state_text:
        raise RuntimeError("startup denied: local_state_dir is not configured")
    local_state_dir = Path(state_text).expanduser().resolve()
    local_appdata_text = os.environ.get("LOCALAPPDATA")
    if not local_appdata_text:
        raise RuntimeError("startup denied: LOCALAPPDATA is unavailable")
    local_appdata = Path(local_appdata_text).expanduser().resolve()
    try:
        local_state_dir.relative_to(local_appdata)
    except ValueError as error:
        raise RuntimeError(
            "startup denied: local_state_dir must be beneath LOCALAPPDATA"
        ) from error
    if not successful_self_test(
        root, self_test_job_id, canonical_folder_id, local_state_dir
    ):
        raise RuntimeError("startup denied: successful self-test receipt not found")
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA is unavailable; this command must run as a Windows user")
    startup = (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )
    startup.mkdir(parents=True, exist_ok=True)
    command_path = startup / "DataBossXDriveWatcher.cmd"
    watcher_script = Path(__file__).with_name("watcher.py").resolve()
    python = Path(sys.executable).resolve()
    command = (
        "@echo off\r\n"
        f'start "DataBossX Drive Watcher" /min "{python}" "{watcher_script}" '
        f'--config "{config_path.resolve()}"\r\n'
    )
    backup_path = backup_file(
        command_path,
        root
        / "config"
        / "startup_backups"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    )
    temporary = command_path.with_suffix(f".cmd.{os.getpid()}.tmp")
    temporary.write_text(command, encoding="utf-8", newline="")
    os.replace(temporary, command_path)
    atomic_write_json(
        root / "config" / "startup_method.json",
        {
            "installed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "method": "current-user Windows Startup folder command file",
            "startup_file": str(command_path),
            "backup_file": str(backup_path) if backup_path else None,
            "disable_instructions": (
                "Move DataBossXDriveWatcher.cmd out of the current user's Startup folder."
            ),
            "administrator_privileges_required": False,
            "registry_modified": False,
        },
    )
    return command_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    detect_parser = subparsers.add_parser("detect")
    detect_parser.add_argument("--folder-id", required=True)
    startup_parser = subparsers.add_parser("install-startup")
    startup_parser.add_argument("--config", type=Path, required=True)
    startup_parser.add_argument("--self-test-job-id", required=True)
    arguments = parser.parse_args(argv)

    if arguments.command == "detect":
        matches = detect(arguments.folder_id)
        print(json.dumps({"matches": [str(path) for path in matches]}, indent=2))
        return 0 if len(matches) == 1 else 2
    try:
        path = install_startup(arguments.config, arguments.self_test_job_id)
    except Exception as error:
        print(f"setup failed closed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"startup installed: {path}")
    print(f"disable by moving this file out of Startup: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
