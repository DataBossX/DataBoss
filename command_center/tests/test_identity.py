"""Regression tests for the server-owned process identity mechanism.

Written before/alongside the identity.py implementation to pin down the
behavior the Windows blockers require: no signal-based liveness probing,
PID-reuse rejection, and a single validator every caller shares.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import identity


class BuildAndRoundtripTests(unittest.TestCase):
    def test_build_identity_has_all_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            ident = identity.build_identity(8765, Path(tmp) / "server.py", Path(tmp))
            for key in ("schema", "pid", "create_time", "python_exe", "server_path",
                        "runtime_dir", "instance_id", "port", "started_at"):
                self.assertIn(key, ident)
            self.assertEqual(ident["pid"], os.getpid())
            self.assertEqual(ident["port"], 8765)
            self.assertEqual(ident["schema"], identity.SCHEMA_VERSION)

    def test_write_then_read_roundtrips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "identity.json"
            ident = identity.build_identity(8765, Path(tmp) / "server.py", Path(tmp))
            identity.write_identity_atomic(ident, path)
            back = identity.read_identity(path)
            self.assertEqual(back["instance_id"], ident["instance_id"])

    def test_write_is_atomic_no_leftover_tmp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "identity.json"
            ident = identity.build_identity(8765, Path(tmp) / "server.py", Path(tmp))
            identity.write_identity_atomic(ident, path)
            leftovers = [p for p in Path(tmp).iterdir() if ".tmp" in p.name]
            self.assertEqual(leftovers, [])


class MalformedReceiptTests(unittest.TestCase):
    def test_missing_file_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, ident = identity.identity_status(Path(tmp) / "nope.json")
            self.assertEqual(status, identity.ABSENT)
            self.assertIsNone(ident)

    def test_garbage_json_is_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "identity.json"
            path.write_text("{not valid json")
            status, ident = identity.identity_status(path)
            self.assertEqual(status, identity.MALFORMED)

    def test_missing_required_field_is_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "identity.json"
            path.write_text(json.dumps({"schema": 1, "pid": 123}))
            status, ident = identity.identity_status(path)
            self.assertEqual(status, identity.MALFORMED)

    def test_wrong_schema_version_is_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "identity.json"
            ident = identity.build_identity(8765, Path(tmp) / "server.py", Path(tmp))
            ident["schema"] = 999
            identity.write_identity_atomic(ident, path)
            status, _ = identity.identity_status(path)
            self.assertEqual(status, identity.MALFORMED)


class LivenessTests(unittest.TestCase):
    def test_dead_pid_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "identity.json"
            ident = identity.build_identity(8765, Path(tmp) / "server.py", Path(tmp))
            # A PID astronomically unlikely to be alive.
            ident["pid"] = 999999
            identity.write_identity_atomic(ident, path)
            status, _ = identity.identity_status(path)
            self.assertEqual(status, identity.STALE)

    def test_running_process_with_matching_fields_is_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            server_path = runtime_dir / "server.py"
            server_path.write_text("# fake")
            path = runtime_dir / "identity.json"
            ident = identity.build_identity(8765, server_path, runtime_dir)
            identity.write_identity_atomic(ident, path)
            status, got = identity.identity_status(
                path, expect_server_path=server_path, expect_runtime_dir=runtime_dir
            )
            self.assertEqual(status, identity.RUNNING)
            self.assertEqual(got["pid"], os.getpid())

    def test_alive_pid_but_wrong_server_path_is_mismatched(self):
        """Simulates PID reuse: our own PID is alive (we ARE a process),
        but the receipt claims a different server_path than the caller
        expects -- this must never be treated as our own server."""
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            real_server_path = runtime_dir / "server.py"
            real_server_path.write_text("# fake")
            other_server_path = runtime_dir / "other" / "server.py"
            path = runtime_dir / "identity.json"
            ident = identity.build_identity(8765, other_server_path, runtime_dir)
            identity.write_identity_atomic(ident, path)
            status, _ = identity.identity_status(
                path, expect_server_path=real_server_path, expect_runtime_dir=runtime_dir
            )
            self.assertEqual(status, identity.MISMATCHED)

    def test_alive_pid_but_wrong_create_time_is_mismatched(self):
        """The core PID-reuse defense: same PID number, but the process
        that currently holds it started at a different time than the
        receipt recorded."""
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            server_path = runtime_dir / "server.py"
            server_path.write_text("# fake")
            path = runtime_dir / "identity.json"
            ident = identity.build_identity(8765, server_path, runtime_dir)
            if ident["create_time"] is None:
                self.skipTest("create_time unavailable on this platform")
            ident["create_time"] = float(ident["create_time"]) + 100000
            identity.write_identity_atomic(ident, path)
            status, _ = identity.identity_status(
                path, expect_server_path=server_path, expect_runtime_dir=runtime_dir
            )
            self.assertEqual(status, identity.MISMATCHED)

    def test_process_alive_never_signals_current_process_to_death(self):
        # Sanity check the safe-probe: checking our own liveness must not
        # actually harm this test process (regression guard against the
        # os.kill(pid, 0)-on-Windows footgun this module replaces).
        self.assertTrue(identity.process_alive(os.getpid()))
        time.sleep(0)  # still alive after the check
        self.assertTrue(identity.process_alive(os.getpid()))


class ClearIdentityTests(unittest.TestCase):
    def test_clear_identity_is_safe_on_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity.clear_identity(Path(tmp) / "nope.json")  # must not raise


if __name__ == "__main__":
    unittest.main()
