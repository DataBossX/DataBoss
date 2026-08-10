"""Focused validation for the DataBossX Command Center.

Uses only stdlib (unittest, urllib, tempfile, threading) -- no test
framework dependency beyond what's already in the repo's CI.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import actions
import db
import discovery
import ai_router
import workers


class DbTests(unittest.TestCase):
    def test_init_is_idempotent_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.db"
            conn = db.connect(path)
            db.init_db(conn)
            db.set_setting(conn, "ai_mode", "SAVE_CREDITS")
            conn.close()

            conn2 = db.connect(path)
            db.init_db(conn2)  # re-init on "restart" must not error
            self.assertEqual(db.get_setting(conn2, "ai_mode"), "SAVE_CREDITS")
            conn2.close()

    def test_missing_db_file_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "new.db"
            conn = db.connect(path)
            db.init_db(conn)
            self.assertTrue(path.exists())
            conn.close()


class DiscoveryTests(unittest.TestCase):
    def test_missing_root_returns_empty_list(self):
        result = discovery.discover_lane("penterra", "/definitely/does/not/exist")
        self.assertEqual(result, [])

    def test_synthetic_project_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proj = root / "Beckham-32"
            proj.mkdir()
            (proj / "Runsheet.xlsx").write_text("x")
            (proj / "Title_Report_v1.docx").write_text("x")
            found = discovery.discover_lane("horizon", str(root))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["project"], "Beckham-32")
            self.assertIn("runsheet", found[0]["evidence_present"])


class ActionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.penterra_root = Path(self.tmp) / "Penterra"
        self.horizon_root = Path(self.tmp) / "Horizon"
        self.penterra_root.mkdir()
        self.horizon_root.mkdir()
        self._env_patch = unittest.mock.patch.dict(os.environ, {
            "DATABOSSX_PENTERRA_ROOT": str(self.penterra_root),
            "DATABOSSX_HORIZON_ROOT": str(self.horizon_root),
        })
        self._env_patch.start()
        self.proj = self.penterra_root / "Proj"
        self.proj.mkdir()
        (self.proj / "a.txt").write_text("hello")

    def tearDown(self):
        self._env_patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unknown_action_refused(self):
        with self.assertRaises(actions.ActionRefused):
            actions.run_action("delete_everything", {"project_path": str(self.proj)}, lane="penterra")

    def test_dangerous_keyword_refused(self):
        with self.assertRaises(actions.ActionRefused):
            actions.run_action(
                "scan_project", {"project_path": str(self.proj), "cmd": "rm -rf /"}, lane="penterra"
            )

    def test_nonexistent_project_path_refused(self):
        with self.assertRaises(actions.ActionRefused):
            actions.run_action(
                "scan_project", {"project_path": str(self.penterra_root / "not-real")}, lane="penterra"
            )

    def test_unknown_lane_refused(self):
        with self.assertRaises(actions.ActionRefused):
            actions.run_action("scan_project", {"project_path": str(self.proj)}, lane="databossx")

    def test_path_outside_configured_root_refused(self):
        outsider = Path(self.tmp) / "not-under-any-root"
        outsider.mkdir()
        with self.assertRaises(actions.ActionRefused):
            actions.run_action("scan_project", {"project_path": str(outsider)}, lane="penterra")

    def test_lane_root_mismatch_refused(self):
        # A real project dir, but under the horizon root while lane says penterra.
        horizon_proj = self.horizon_root / "HProj"
        horizon_proj.mkdir()
        with self.assertRaises(actions.ActionRefused):
            actions.run_action("scan_project", {"project_path": str(horizon_proj)}, lane="penterra")

    def test_dot_dot_traversal_refused(self):
        traversal = str(self.penterra_root / "Proj" / ".." / ".." / "Horizon")
        with self.assertRaises(actions.ActionRefused):
            actions.run_action("scan_project", {"project_path": traversal}, lane="penterra")

    def test_operating_on_root_itself_refused(self):
        with self.assertRaises(actions.ActionRefused):
            actions.run_action("scan_project", {"project_path": str(self.penterra_root)}, lane="penterra")

    def test_nested_path_beyond_direct_child_refused(self):
        nested = self.proj / "subdir"
        nested.mkdir()
        with self.assertRaises(actions.ActionRefused):
            actions.run_action("scan_project", {"project_path": str(nested)}, lane="penterra")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink not supported on this platform")
    def test_symlink_escape_refused(self):
        outsider = Path(self.tmp) / "secret-outside"
        outsider.mkdir()
        link = self.penterra_root / "LinkedProj"
        try:
            os.symlink(outsider, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation not permitted in this environment")
        with self.assertRaises(actions.ActionRefused):
            actions.run_action("scan_project", {"project_path": str(link)}, lane="penterra")

    def test_build_worklist_refused_until_setup_confirmed(self):
        with self.assertRaises(actions.ActionRefused):
            actions.run_action(
                "build_worklist", {"project_path": str(self.proj)}, lane="penterra", setup_confirmed=False
            )

    def test_build_worklist_only_writes_inside_working_subdir(self):
        result = actions.run_action(
            "build_worklist", {"project_path": str(self.proj)}, lane="penterra", setup_confirmed=True
        )
        self.assertTrue(result.ok)
        self.assertEqual(len(result.files_changed), 1)
        written = Path(result.files_changed[0])
        self.assertEqual(written.parent.name, discovery.WORKING_SUBDIR)
        # original source file must be untouched
        self.assertEqual((self.proj / "a.txt").read_text(), "hello")

    def test_scan_project_never_writes(self):
        before = set(os.listdir(self.proj))
        actions.run_action("scan_project", {"project_path": str(self.proj)}, lane="penterra")
        after = set(os.listdir(self.proj))
        self.assertEqual(before, after)

    def test_read_only_action_allowed_without_setup_confirmed(self):
        # Read-only actions must not be blocked by the setup gate.
        result = actions.run_action(
            "scan_project", {"project_path": str(self.proj)}, lane="penterra", setup_confirmed=False
        )
        self.assertTrue(result.ok)


class AiRouterTests(unittest.TestCase):
    def test_local_only_mode_never_returns_egress_provider(self):
        picked = ai_router.route("classify", mode="LOCAL_ONLY")
        self.assertFalse(picked["data_egress"])

    def test_save_credits_prefers_free(self):
        picked = ai_router.route("scan", mode="SAVE_CREDITS")
        self.assertEqual(picked["cost_class"], "FREE")

    def test_local_model_detection_does_not_raise_without_credentials(self):
        os.environ["DATABOSSX_LOCAL_MODEL_URL"] = "http://127.0.0.1:1"  # unreachable on purpose
        result = ai_router.detect_local_model()
        self.assertIn("available", result)
        self.assertFalse(result["available"])


class WorkerOwnershipTests(unittest.TestCase):
    def test_stop_refused_for_unregistered_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(Path(tmp) / "t.db")
            db.init_db(conn)
            with self.assertRaises(PermissionError):
                workers.stop_databossx_worker(conn, 999999, registered_pids=set())
            conn.close()

    def test_stop_allowed_for_registered_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(Path(tmp) / "t.db")
            db.init_db(conn)
            workers.register_worker(conn, 4242, "scan_project")
            ok = workers.stop_databossx_worker(conn, 4242, registered_pids={4242})
            self.assertTrue(ok)
            conn.close()


class ServerIntegrationTests(unittest.TestCase):
    """Spins up the real HTTP server on a scratch DB and hits it over HTTP."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["DATABOSSX_DB_PATH"] = str(Path(cls.tmp) / "server_test.db")
        os.environ["DATABOSSX_PENTERRA_ROOT"] = str(Path(cls.tmp) / "Penterra")
        os.environ["DATABOSSX_HORIZON_ROOT"] = str(Path(cls.tmp) / "Horizon")
        Path(os.environ["DATABOSSX_PENTERRA_ROOT"]).mkdir(parents=True)
        Path(os.environ["DATABOSSX_HORIZON_ROOT"]).mkdir(parents=True)

        import importlib
        import server as server_module
        importlib.reload(server_module)  # pick up the env vars set above
        cls.server_module = server_module
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server_module.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)
        # Captured before any other test populates the shared scratch roots
        # with synthetic projects -- later tests must not depend on an empty
        # filesystem, only this snapshot may assert "no projects yet".
        with urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/api/state", timeout=5) as r:
            cls.initial_state = json.loads(r.read())

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as r:
            return json.loads(r.read())

    def _post(self, path, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_build_worklist_refused_before_confirm_over_http(self):
        # Runs early alphabetically ('b' < 'f'), before test_full_action_roundtrip
        # confirms setup for the rest of the class's shared server/db.
        setup = self._get("/api/setup")
        self.assertIn("read_roots", setup)
        self.assertIn("penterra", setup["read_roots"])
        self.assertFalse(setup["setup_confirmed"])

        proj_dir = Path(os.environ["DATABOSSX_PENTERRA_ROOT"]) / "Unconfirmed-Proj"
        proj_dir.mkdir()
        status, body = self._post(
            "/api/actions/run",
            {"task": "build_worklist", "project_path": str(proj_dir), "lane": "penterra", "project": "Unconfirmed-Proj"},
        )
        self.assertEqual(status, 403)
        self.assertTrue(body.get("refused"))
        self.assertIn("setup", body.get("reason", "").lower())

    def test_internal_error_response_has_no_traceback_or_local_paths(self):
        # /api/state calls db.get_setting -- force it to blow up and confirm the
        # HTTP response never leaks a traceback or a local filesystem path.
        with unittest.mock.patch.object(
            self.server_module.db, "get_setting", side_effect=RuntimeError("boom: /secret/local/path")
        ):
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/state", method="GET")
            try:
                urllib.request.urlopen(req, timeout=5)
                self.fail("expected HTTP 500")
            except urllib.error.HTTPError as e:
                status = e.code
                body = json.loads(e.read())
        self.assertEqual(status, 500)
        self.assertEqual(body.get("error"), "internal_error")
        self.assertIn("error_id", body)
        self.assertNotIn("trace", body)
        self.assertNotIn("/secret/local/path", json.dumps(body))

    def test_health(self):
        self.assertEqual(self._get("/api/health")["status"], "ok")

    def test_home_route_serves_html(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=5) as r:
            body = r.read().decode()
            self.assertIn("DataBossX Command Center", body)

    def test_static_assets_serve(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/static/app.css", timeout=5) as r:
            self.assertEqual(r.status, 200)
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/static/app.js", timeout=5) as r:
            self.assertEqual(r.status, 200)

    def test_state_with_no_projects(self):
        # Snapshot taken in setUpClass before any test created a project.
        self.assertEqual(self.initial_state["lanes"]["penterra"], [])
        self.assertIsNone(self.initial_state["next_best_move"]["project"])

    def test_dangerous_action_refused_over_http(self):
        status, body = self._post("/api/actions/run", {"task": "nonexistent_task", "project_path": "/tmp"})
        self.assertEqual(status, 403)
        self.assertTrue(body.get("refused"))

    def test_source_path_missing_refused_over_http(self):
        status, body = self._post(
            "/api/actions/run",
            {"task": "scan_project", "project_path": str(Path(os.environ["DATABOSSX_PENTERRA_ROOT"]) / "nope"), "lane": "penterra"},
        )
        self.assertEqual(status, 403)
        self.assertTrue(body.get("refused"))

    def test_path_escape_refused_over_http(self):
        status, body = self._post(
            "/api/actions/run",
            {"task": "scan_project", "project_path": str(Path(os.environ["DATABOSSX_HORIZON_ROOT"])), "lane": "penterra"},
        )
        self.assertEqual(status, 403)
        self.assertTrue(body.get("refused"))

    def test_full_action_roundtrip_produces_receipt(self):
        confirm_status, confirm_body = self._post("/api/setup/confirm", {})
        self.assertEqual(confirm_status, 200)
        self.assertTrue(confirm_body["setup_confirmed"])

        proj_dir = Path(os.environ["DATABOSSX_PENTERRA_ROOT"]) / "Synthetic-Demo"
        proj_dir.mkdir()
        (proj_dir / "Runsheet.xlsx").write_text("x")
        status, body = self._post(
            "/api/actions/run",
            {"task": "build_worklist", "project_path": str(proj_dir), "lane": "penterra", "project": "Synthetic-Demo"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        receipts = self._get("/api/receipts")["receipts"]
        self.assertTrue(any(r["project"] == "Synthetic-Demo" for r in receipts))

    def test_mode_switch_local_only(self):
        status, body = self._post("/api/mode", {"mode": "LOCAL_ONLY"})
        self.assertEqual(status, 200)
        self.assertEqual(body["mode"], "LOCAL_ONLY")

    def test_workers_endpoint_labels_ownership(self):
        data = self._get("/api/workers")
        self.assertIn("owned", data)
        self.assertIn("observed", data)


if __name__ == "__main__":
    unittest.main()
