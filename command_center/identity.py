"""Server-owned process identity: replaces the unsafe os.kill(pid, 0)
liveness probe and bare PID/exe-name checks that a stale PID reuse could
fool.

On Windows, os.kill(pid, 0) does not "just check" -- CPython's Windows
implementation of os.kill sends every signal (including 0) via
TerminateProcess, so a naive liveness probe there can actually kill an
unrelated process that happens to have reused a stale PID. This module
never signals a process to check on it. Liveness and identity are both
read via read-only OS queries (ctypes Win32 calls on Windows, /proc or
os.kill(pid, 0) -- which is safe on POSIX -- elsewhere).

One JSON receipt, written atomically, is the single source of truth for
"is this our server". START, STOP, REPAIR, DIAGNOSTICS, and the
single-instance lock all call identity_status() and compare against the
same fields -- no code path may taskkill/terminate based on PID, image
name, or a command-line substring alone.
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path

SCHEMA_VERSION = 1

# Fields that must both be present and match for a receipt to describe
# THIS running process. If any of these mismatch, the PID is either dead
# or has been reused by an unrelated process -- either way, not ours.
_MATCH_FIELDS = ("pid", "create_time", "python_exe", "server_path", "runtime_dir")

RUNNING = "RUNNING"          # verified: PID alive AND every identity field matches
STALE = "STALE"              # PID is not alive -- receipt is safe to reclaim
MISMATCHED = "MISMATCHED"    # PID is alive but identity fields don't match -- NOT ours
MALFORMED = "MALFORMED"      # receipt file unreadable/invalid -- treat as absent, refuse to trust it
ABSENT = "ABSENT"            # no receipt file at all


def _win32_open_process(pid: int):
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    return handle, kernel32


def _win32_process_alive_and_create_time(pid: int):
    """Read-only Win32 query. Returns (alive: bool, create_time: float|None).

    Never sends a signal and never opens the process for termination
    rights -- PROCESS_QUERY_LIMITED_INFORMATION is read-only metadata
    access. A handle of 0 means the PID does not exist or we lack access
    (treated as not-alive-to-us, which is the safe default: we will never
    claim ownership of a process we cannot positively verify).
    """
    import ctypes
    from ctypes import wintypes

    handle, kernel32 = _win32_open_process(pid)
    if not handle:
        return False, None
    try:
        STILL_ACTIVE = 259
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False, None
        if exit_code.value != STILL_ACTIVE:
            return False, None

        creation = wintypes.FILETIME()
        exit_t = wintypes.FILETIME()
        kernel_t = wintypes.FILETIME()
        user_t = wintypes.FILETIME()
        ok = kernel32.GetProcessTimes(
            handle, ctypes.byref(creation), ctypes.byref(exit_t),
            ctypes.byref(kernel_t), ctypes.byref(user_t),
        )
        if not ok:
            return True, None
        create_ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        return True, float(create_ticks)
    finally:
        kernel32.CloseHandle(handle)


def _posix_process_alive_and_create_time(pid: int):
    """POSIX: os.kill(pid, 0) is a genuine no-op existence check here (it
    only raises OSError, it does not terminate anything on POSIX). Create
    time comes from /proc when available (Linux); otherwise we fall back
    to alive-only (create_time None), which downgrades identity matching
    to PID+path equality -- acceptable off-Windows since production runs
    on Windows.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False, None
    except PermissionError:
        return True, None  # exists, but we can't see its metadata
    except OSError:
        return False, None

    stat_path = Path(f"/proc/{pid}/stat")
    try:
        raw = stat_path.read_text()
        # field 22 (starttime) sits after the ")" that closes the comm field,
        # which may itself contain spaces/parens.
        after = raw.rsplit(")", 1)[1].split()
        starttime = after[19]  # index 0 is field 3; starttime is field 22
        return True, float(starttime)
    except (FileNotFoundError, IndexError, ValueError, OSError):
        return True, None


def process_alive_and_create_time(pid: int):
    if sys.platform == "win32":
        return _win32_process_alive_and_create_time(pid)
    return _posix_process_alive_and_create_time(pid)


def process_alive(pid: int) -> bool:
    alive, _ = process_alive_and_create_time(pid)
    return alive


def build_identity(port: int, server_path: Path, runtime_dir: Path) -> dict:
    now = time.time()
    pid = os.getpid()
    _, create_time = process_alive_and_create_time(pid)
    return {
        "schema": SCHEMA_VERSION,
        "pid": pid,
        "create_time": create_time,
        "python_exe": os.path.realpath(sys.executable),
        "server_path": str(Path(server_path).resolve()),
        "runtime_dir": str(Path(runtime_dir).resolve()),
        "instance_id": uuid.uuid4().hex,
        "port": port,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "started_epoch": now,
    }


def write_identity_atomic(identity: dict, path: Path) -> None:
    """Write-then-rename so a reader never observes a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(identity, indent=2), encoding="utf-8")
    os.replace(tmp, path)


_REQUIRED_TYPES = {
    "schema": int,
    "pid": int,
    "python_exe": str,
    "server_path": str,
    "runtime_dir": str,
    "instance_id": str,
    "port": int,
    "started_at": str,
}


def _valid_schema(identity) -> bool:
    if not isinstance(identity, dict):
        return False
    for key, typ in _REQUIRED_TYPES.items():
        if key not in identity or not isinstance(identity[key], typ):
            return False
    if identity["schema"] != SCHEMA_VERSION:
        return False
    if identity["pid"] <= 0 or identity["port"] <= 0:
        return False
    return True


def read_identity(path: Path) -> dict:
    """Returns a dict on success, or None if the receipt is absent or
    malformed. Never raises -- a bad receipt must never crash a launcher
    or be trusted, only be treated as MALFORMED/ABSENT by identity_status.
    """
    path = Path(path)
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not _valid_schema(data):
        return None
    return data


def identity_status(path: Path, expect_server_path: Path = None, expect_runtime_dir: Path = None):
    """The single validator every caller (single-instance lock, START,
    STOP, REPAIR, DIAGNOSTICS) must use. Returns (status, identity|None).

    status is one of ABSENT, MALFORMED, STALE, MISMATCHED, RUNNING.
    Only RUNNING means "this PID is verified to be our server" -- every
    other status means the caller may reclaim the receipt file but must
    never act on the underlying PID.
    """
    path = Path(path)
    if not path.exists():
        return ABSENT, None
    raw_identity = None
    try:
        raw_identity = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return MALFORMED, None
    if not _valid_schema(raw_identity):
        return MALFORMED, None

    pid = raw_identity["pid"]
    alive, live_create_time = process_alive_and_create_time(pid)
    if not alive:
        return STALE, raw_identity

    mismatches = []
    if expect_server_path is not None:
        if raw_identity["server_path"] != str(Path(expect_server_path).resolve()):
            mismatches.append("server_path")
    if expect_runtime_dir is not None:
        if raw_identity["runtime_dir"] != str(Path(expect_runtime_dir).resolve()):
            mismatches.append("runtime_dir")

    recorded_create_time = raw_identity.get("create_time")
    if recorded_create_time is not None and live_create_time is not None:
        if abs(float(recorded_create_time) - float(live_create_time)) > 2.0:
            mismatches.append("create_time")

    if mismatches:
        return MISMATCHED, raw_identity
    return RUNNING, raw_identity


def clear_identity(path: Path) -> None:
    Path(path).unlink(missing_ok=True)
