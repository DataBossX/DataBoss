"""Single CLI entry point the .bat launchers use for identity decisions.

START, STOP, REPAIR, and DIAGNOSTICS all shell out to this script instead
of re-implementing PID/name matching in batch. That guarantees every
launcher path runs through the exact same identity.identity_status()
validator as the server's own single-instance lock -- there is no second,
looser check anywhere.

Every subcommand prints one line of JSON to stdout and sets an exit code:
  0 = safe / no action needed / action completed
  1 = SAFETY REFUSAL -- a live, unowned/mismatched process was left untouched
  2 = usage error
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import discovery
import identity

BASE_DIR = Path(__file__).parent
DEFAULT_SERVER_PATH = BASE_DIR / "server.py"


def _receipt_path(runtime_dir: Path) -> Path:
    return runtime_dir / "identity.json"


def _emit(obj: dict, exit_code: int = 0):
    print(json.dumps(obj))
    sys.exit(exit_code)


def cmd_status(args):
    runtime_dir = Path(args.runtime_dir)
    status, ident = identity.identity_status(
        _receipt_path(runtime_dir), expect_server_path=args.server_path, expect_runtime_dir=runtime_dir
    )
    _emit({"status": status, "identity": ident}, 0)


def _terminate_pid(pid: int) -> bool:
    if sys.platform == "win32":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True, timeout=15
        )
        return result.returncode == 0
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if not identity.process_alive(pid):
                return True
            time.sleep(0.25)
        os.kill(pid, signal.SIGKILL)
        return True
    except ProcessLookupError:
        return True
    except OSError:
        return False


def cmd_stop(args):
    runtime_dir = Path(args.runtime_dir)
    receipt_path = _receipt_path(runtime_dir)
    status, ident = identity.identity_status(
        receipt_path, expect_server_path=args.server_path, expect_runtime_dir=runtime_dir
    )
    if status == identity.ABSENT:
        _emit({"status": status, "action": "none", "message": "No identity receipt -- nothing to stop."}, 0)
    if status == identity.STALE:
        identity.clear_identity(receipt_path)
        _emit({"status": status, "action": "cleared_stale_receipt", "message": "PID in receipt is not alive."}, 0)
    if status == identity.MALFORMED:
        _emit({
            "status": status, "action": "refused",
            "message": "SAFETY REFUSAL: identity receipt is malformed/unverifiable. "
                       "No process was touched. Run REPAIR to clear it, or investigate manually.",
        }, 1)
    if status == identity.MISMATCHED:
        _emit({
            "status": status, "action": "refused", "identity": ident,
            "message": f"SAFETY REFUSAL: PID {ident['pid']} is alive but its identity "
                       "(creation time / executable / server path / runtime dir) does not "
                       "match this receipt -- it has likely been reused by an unrelated "
                       "process. Left untouched.",
        }, 1)
    # RUNNING
    pid = ident["pid"]
    ok = _terminate_pid(pid)
    if ok:
        identity.clear_identity(receipt_path)
        port_txt = runtime_dir / "port.txt"
        port_txt.unlink(missing_ok=True)
        _emit({"status": status, "action": "stopped", "pid": pid}, 0)
    _emit({"status": status, "action": "failed", "pid": pid, "message": "taskkill/terminate did not succeed."}, 1)


def cmd_repair(args):
    runtime_dir = Path(args.runtime_dir)
    receipt_path = _receipt_path(runtime_dir)
    status, ident = identity.identity_status(
        receipt_path, expect_server_path=args.server_path, expect_runtime_dir=runtime_dir
    )
    if status in (identity.ABSENT,):
        _emit({"status": status, "action": "none", "message": "No receipt present -- nothing to repair."}, 0)
    if status in (identity.STALE, identity.MALFORMED):
        identity.clear_identity(receipt_path)
        (runtime_dir / "port.txt").unlink(missing_ok=True)
        _emit({"status": status, "action": "cleared", "message": "Cleared a receipt that did not describe a live process."}, 0)
    if status == identity.MISMATCHED:
        _emit({
            "status": status, "action": "refused", "identity": ident,
            "message": f"SAFETY REFUSAL: PID {ident['pid']} is alive but is not our server "
                       "(identity mismatch). Repair will not alter it. Investigate manually if needed.",
        }, 1)
    # RUNNING
    _emit({
        "status": status, "action": "none", "identity": ident,
        "message": "A verified DataBossX server is currently running -- nothing to repair. "
                   "Run STOP first if you want to repair while stopped.",
    }, 0)


def cmd_diagnostics(args):
    runtime_dir = Path(args.runtime_dir)
    receipt_path = _receipt_path(runtime_dir)
    status, ident = identity.identity_status(
        receipt_path, expect_server_path=args.server_path, expect_runtime_dir=runtime_dir
    )
    _emit({
        "status": status,
        "identity": ident,
        "effective_roots": dict(discovery.get_roots()),
        "runtime_dir": str(runtime_dir.resolve()) if runtime_dir.exists() else str(runtime_dir),
        "server_path": str(Path(args.server_path).resolve()),
        "db_path": os.environ.get("DATABOSSX_DB_PATH", str(runtime_dir / "databossx.db")),
        "sandbox_mode": os.environ.get("DATABOSSX_SANDBOX_MODE", "0") == "1",
    }, 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--server-path", default=str(DEFAULT_SERVER_PATH))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("stop")
    sub.add_parser("repair")
    sub.add_parser("diagnostics")
    args = parser.parse_args()

    handlers = {
        "status": cmd_status, "stop": cmd_stop, "repair": cmd_repair, "diagnostics": cmd_diagnostics,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
