"""Regression tests for identity_cli.py -- the shared CLI wrapper the
.bat launchers (START/STOP/REPAIR/DIAGNOSTICS) all call so every launcher
path goes through the exact same identity.identity_status() validator.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CC_DIR = Path(__file__).parent.parent
CLI = CC_DIR / "identity_cli.py"


def run_cli(runtime_dir, *args):
    result = subprocess.run(
        [sys.executable, str(CLI), "--runtime-dir", str(runtime_dir), *args],
        capture_output=True, text=True, timeout=15,
    )
    return result.returncode, json.loads(result.stdout.strip())


class StatusCommandTests(unittest.TestCase):
    def test_status_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = run_cli(tmp, "status")
            self.assertEqual(rc, 0)
            self.assertEqual(out["status"], "ABSENT")

    def test_status_running_for_this_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            sys.path.insert(0, str(CC_DIR))
            import identity
            server_path = Path(tmp) / "server.py"
            server_path.write_text("# fake")
            ident = identity.build_identity(8765, server_path, Path(tmp))
            identity.write_identity_atomic(ident, Path(tmp) / "identity.json")
            rc, out = run_cli(tmp, "--server-path", str(server_path), "status")
            self.assertEqual(rc, 0)
            self.assertEqual(out["status"], "RUNNING")
            self.assertEqual(out["identity"]["pid"], os.getpid())


class StopCommandTests(unittest.TestCase):
    def test_stop_on_absent_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = run_cli(tmp, "stop")
            self.assertEqual(rc, 0)
            self.assertEqual(out["action"], "none")

    def test_stop_refuses_on_mismatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            sys.path.insert(0, str(CC_DIR))
            import identity
            server_path = Path(tmp) / "server.py"
            server_path.write_text("# fake")
            ident = identity.build_identity(8765, server_path, Path(tmp))
            ident["server_path"] = str(Path(tmp) / "some-other-server.py")
            identity.write_identity_atomic(ident, Path(tmp) / "identity.json")
            rc, out = run_cli(tmp, "--server-path", str(server_path), "stop")
            self.assertEqual(rc, 1)
            self.assertEqual(out["status"], "MISMATCHED")
            self.assertEqual(out["action"], "refused")
            self.assertTrue((Path(tmp) / "identity.json").exists())  # untouched

    def test_stop_clears_malformed_without_touching_any_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "identity.json").write_text("not json")
            rc, out = run_cli(tmp, "stop")
            self.assertEqual(rc, 1)
            self.assertEqual(out["status"], "MALFORMED")


class RepairCommandTests(unittest.TestCase):
    def test_repair_clears_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            sys.path.insert(0, str(CC_DIR))
            import identity
            server_path = Path(tmp) / "server.py"
            server_path.write_text("# fake")
            ident = identity.build_identity(8765, server_path, Path(tmp))
            ident["pid"] = 999999
            identity.write_identity_atomic(ident, Path(tmp) / "identity.json")
            rc, out = run_cli(tmp, "--server-path", str(server_path), "repair")
            self.assertEqual(rc, 0)
            self.assertEqual(out["status"], "STALE")
            self.assertFalse((Path(tmp) / "identity.json").exists())

    def test_repair_refuses_on_mismatched_without_touching_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            sys.path.insert(0, str(CC_DIR))
            import identity
            server_path = Path(tmp) / "server.py"
            server_path.write_text("# fake")
            ident = identity.build_identity(8765, server_path, Path(tmp))
            ident["server_path"] = str(Path(tmp) / "some-other-server.py")
            identity.write_identity_atomic(ident, Path(tmp) / "identity.json")
            rc, out = run_cli(tmp, "--server-path", str(server_path), "repair")
            self.assertEqual(rc, 1)
            self.assertEqual(out["status"], "MISMATCHED")
            self.assertTrue(identity.process_alive(os.getpid()))  # our own process untouched


class DiagnosticsCommandTests(unittest.TestCase):
    def test_diagnostics_reports_effective_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["DATABOSSX_PENTERRA_ROOT"] = "/scratch/penterra"
            env["DATABOSSX_HORIZON_ROOT"] = "/scratch/horizon"
            result = subprocess.run(
                [sys.executable, str(CLI), "--runtime-dir", tmp, "diagnostics"],
                capture_output=True, text=True, timeout=15, env=env,
            )
            out = json.loads(result.stdout.strip())
            self.assertEqual(out["effective_roots"]["penterra"], "/scratch/penterra")
            self.assertEqual(out["effective_roots"]["horizon"], "/scratch/horizon")


if __name__ == "__main__":
    unittest.main()
