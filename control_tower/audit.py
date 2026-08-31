"""The Gate 0 read-only audit.

Nothing in this module writes outside its own append-only run directory, and
nothing here opens a workbook. Files are hashed by streaming bytes, which does
not touch Excel and cannot trigger a recalculation or a save.

Every item resolves to one of three dispositions:

``OBSERVED``      we looked and this is what is there
``UNREACHABLE``   this host cannot see the thing being asked about
``MISMATCH``      we looked and it disagrees with the pinned expectation

``UNREACHABLE`` is deliberately not a pass. A cloud lane auditing a Windows
workstation must say it cannot see it, rather than reporting a clean result.
"""

import hashlib
import os
import platform
import subprocess

from .constants import (
    COMPLETED_FOLDER_ID,
    QUEUE_FOLDER_ID,
    RECEIPTS_FOLDER_ID,
    V12_EXPECTED_SHA256,
    WATCHER_OUTPUT_FOLDER_ID,
)

OBSERVED = "OBSERVED"
UNREACHABLE = "UNREACHABLE"
MISMATCH = "MISMATCH"

_LOCK_PREFIX = "~$"


def is_windows():
    return platform.system().lower().startswith("win")


def hash_file(path, chunk_size=1024 * 1024):
    """Stream a file's SHA-256 without opening it in any application."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().upper()


def audit_expected_file(path, expected_sha256):
    """Verify one pinned artifact by exact path, size, and digest."""
    if not path:
        return {"status": UNREACHABLE, "reason": "no path pinned"}
    if not os.path.isabs(path) and not is_windows():
        return {
            "status": UNREACHABLE,
            "reason": "path is host-relative and this host is not the target",
            "path": path,
        }
    if not os.path.exists(path):
        return {"status": UNREACHABLE, "reason": "path not present on this host", "path": path}
    stat = os.stat(path)
    actual = hash_file(path)
    item = {
        "path": path,
        "bytes": stat.st_size,
        "mtime_epoch": stat.st_mtime,
        "sha256": actual,
        "expected_sha256": expected_sha256,
    }
    item["status"] = OBSERVED if actual == expected_sha256 else MISMATCH
    return item


def _run(command):
    """Run a read-only host query, tolerating absence of the tool."""
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout


def audit_processes():
    """Look for Excel and DataBossX processes. Read-only; kills nothing."""
    if not is_windows():
        return {
            "status": UNREACHABLE,
            "reason": "Windows process table not visible from this host",
            "host": platform.system(),
        }
    out = _run(["tasklist"])
    if out is None:
        return {"status": UNREACHABLE, "reason": "tasklist unavailable"}
    lowered = out.lower()
    return {
        "status": OBSERVED,
        "excel_running": "excel.exe" in lowered,
        "databossx_running": "databossx" in lowered,
    }


def audit_services_and_tasks():
    if not is_windows():
        return {
            "status": UNREACHABLE,
            "reason": "Windows services and scheduled tasks not visible from this host",
        }
    services = _run(["sc", "query", "type=", "service", "state=", "all"]) or ""
    tasks = _run(["schtasks", "/query", "/fo", "LIST"]) or ""
    lowered = (services + tasks).lower()
    return {
        "status": OBSERVED,
        "databossx_service_present": "databossx" in lowered,
        "databossx_scheduled_task_present": "databossx" in tasks.lower(),
    }


def audit_workbook_locks(directory):
    """Detect Excel owner-lock files without opening any workbook."""
    if not directory or not os.path.isdir(directory):
        return {"status": UNREACHABLE, "reason": "directory not present on this host"}
    locks = []
    for root, _dirs, files in os.walk(directory):
        for name in files:
            if name.startswith(_LOCK_PREFIX):
                locks.append(os.path.join(root, name))
    return {"status": OBSERVED, "lock_files": locks, "lock_count": len(locks)}


def audit_repository(repo_path):
    """Branch, HEAD, cleanliness, and worktrees, by porcelain output only."""
    if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
        return {"status": UNREACHABLE, "reason": "no git repository at that path"}

    def git(*args):
        out = _run(["git", "-C", repo_path] + list(args))
        return (out or "").strip()

    status = git("status", "--porcelain=v1")
    return {
        "status": OBSERVED,
        "head_commit": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "clean": status == "",
        "dirty_entries": [line for line in status.splitlines() if line],
        "worktrees": [line for line in git("worktree", "list").splitlines() if line],
    }


def audit_drive_surface(client):
    """Enumerate the control folders. Read-only; creates nothing."""
    surface = {}
    for label, folder_id in (
        ("queue", QUEUE_FOLDER_ID),
        ("receipts", RECEIPTS_FOLDER_ID),
        ("watcher_output", WATCHER_OUTPUT_FOLDER_ID),
        ("completed", COMPLETED_FOLDER_ID),
    ):
        try:
            children = client.list_children(folder_id)
        except Exception as exc:  # noqa: BLE001 - report, never crash the audit
            surface[label] = {"status": UNREACHABLE, "reason": str(exc)}
            continue
        surface[label] = {
            "status": OBSERVED,
            "folder_id": folder_id,
            "child_count": len(children),
            "titles": sorted(child.get("title", "") for child in children),
        }
    return surface


def run_audit(client=None, v12_path=None, repo_path=None, workbook_dir=None):
    """Assemble the full Gate 0 audit for this host."""
    report = {
        "audit_mode": "READ_ONLY",
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "is_windows": is_windows(),
            "node": platform.node(),
        },
        "v12": audit_expected_file(v12_path, V12_EXPECTED_SHA256),
        "processes": audit_processes(),
        "services_and_tasks": audit_services_and_tasks(),
        "workbook_locks": audit_workbook_locks(workbook_dir),
        "repository": audit_repository(repo_path),
        "drive_surface": audit_drive_surface(client) if client is not None else {
            "status": UNREACHABLE,
            "reason": "no Drive client supplied",
        },
        "workbook_opened": False,
        "workbook_mutated": False,
    }

    v12_status = report["v12"].get("status")
    if v12_status == OBSERVED:
        report["v12_ruling"] = "VERIFIED_EXACT"
    elif v12_status == MISMATCH:
        report["v12_ruling"] = "HASH_MISMATCH_FAIL_CLOSED"
    else:
        report["v12_ruling"] = "NOT_VERIFIED_UNREACHABLE"

    unreachable = [
        key
        for key, value in report.items()
        if isinstance(value, dict) and value.get("status") == UNREACHABLE
    ]
    report["unreachable_items"] = sorted(unreachable)
    report["audit_completeness"] = (
        "COMPLETE" if not unreachable else "PARTIAL_HOST_MISMATCH"
    )
    return report
