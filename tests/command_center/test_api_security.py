"""HTTP-layer red-team tests against a real server instance.

The server is started on an ephemeral loopback port and driven with urllib, so
these exercise the actual socket path -- headers, cookies, CSRF, and status
codes -- rather than calling the handler directly.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from command_center.errors import NotAuthorized
from command_center.http_api import ControlCenterApp, make_handler
from command_center.kernel import ControlKernel

from .support import SERVICE_ROOT  # noqa: F401  (ensures sys.path is set)


class ApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from http.server import ThreadingHTTPServer

        cls.workdir = tempfile.mkdtemp(prefix="dbx-cc-api-")
        cls.kernel = ControlKernel.open(os.path.join(cls.workdir, "cc.db"))
        cls.app = ControlCenterApp(
            cls.kernel,
            allowed_origins=("http://127.0.0.1:8787",),
            workroot=os.path.join(cls.workdir, "runner"),
        )
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.app))
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.kernel.conn.close()
        shutil.rmtree(cls.workdir, ignore_errors=True)

    def call(self, path, method="GET", body=None, headers=None, cookie=None):
        data = json.dumps(body).encode() if body is not None else None
        hdrs = {"Content-Type": "application/json", **(headers or {})}
        if cookie:
            hdrs["Cookie"] = cookie
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=hdrs)
        try:
            res = urllib.request.urlopen(req, timeout=25)
            return res.status, json.loads(res.read() or b"{}"), dict(res.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}"), dict(exc.headers)

    def login(self, user_id="ryan"):
        status, payload, headers = self.call(
            "/api/session", "POST", {"user_id": user_id, "device_id": "test-device"}
        )
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"].split(";")[0]
        return cookie, payload["csrf"]


class UnauthenticatedAccessTests(ApiTestCase):
    def test_protected_routes_reject_anonymous_requests(self):
        for path in ("/api/posture", "/api/best-moves", "/api/jobs",
                     "/api/audit", "/api/watchers", "/api/holds"):
            status, payload, _ = self.call(path)
            self.assertEqual(status, 401, f"{path} should require authentication")
            self.assertEqual(payload["error"], "NOT_AUTHENTICATED")

    def test_state_changing_routes_reject_anonymous_requests(self):
        status, payload, _ = self.call("/api/run-slice", "POST", {})
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "NOT_AUTHENTICATED")

    def test_health_reveals_nothing_sensitive(self):
        status, payload, _ = self.call("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(set(payload), {"status", "policy_version"})

    def test_unknown_identity_is_refused(self):
        status, _, _ = self.call("/api/session", "POST", {"user_id": "attacker"})
        self.assertEqual(status, 401)


class SessionAndCsrfTests(ApiTestCase):
    def test_session_cookie_is_httponly_and_samesite_strict(self):
        _, _, headers = self.call("/api/session", "POST",
                                  {"user_id": "ryan", "device_id": "d"})
        cookie_header = headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("SameSite=Strict", cookie_header)
        self.assertIn("Path=/", cookie_header)

    def test_state_change_without_csrf_token_is_refused(self):
        cookie, _ = self.login()
        status, payload, _ = self.call("/api/run-slice", "POST", {}, cookie=cookie)
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "CSRF_FAILED")

    def test_state_change_with_wrong_csrf_token_is_refused(self):
        cookie, _ = self.login()
        status, payload, _ = self.call("/api/run-slice", "POST", {},
                                       headers={"X-DBX-CSRF": "wrong-token"}, cookie=cookie)
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "CSRF_FAILED")

    def test_expired_session_is_refused(self):
        cookie, csrf = self.login()
        token = cookie.split("=", 1)[1]
        self.app.sessions.expire_now(token)
        status, payload, _ = self.call("/api/posture", cookie=cookie)
        self.assertEqual(status, 401)
        status, _, _ = self.call("/api/run-slice", "POST", {},
                                 headers={"X-DBX-CSRF": csrf}, cookie=cookie)
        self.assertEqual(status, 401)

    def test_revoked_session_is_refused(self):
        cookie, _ = self.login()
        self.call("/api/session", "DELETE", {}, cookie=cookie)
        # The session is gone, so the follow-up fails authentication.
        status, _, _ = self.call("/api/posture", cookie=cookie)
        self.assertIn(status, (401, 403))


class SecurityHeaderTests(ApiTestCase):
    def test_strict_csp_and_hardening_headers_are_present(self):
        _, _, headers = self.call("/api/health")
        csp = headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("unsafe-eval", csp)
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_cors_is_never_wildcard_with_credentials(self):
        _, _, headers = self.call("/api/health",
                                  headers={"Origin": "https://evil.example.com"})
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_cors_allows_only_the_exact_configured_origin(self):
        _, _, headers = self.call("/api/health",
                                  headers={"Origin": "http://127.0.0.1:8787"})
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://127.0.0.1:8787")
        self.assertEqual(headers["Access-Control-Allow-Credentials"], "true")
        self.assertNotEqual(headers["Access-Control-Allow-Origin"], "*")

    def test_no_secret_status_endpoint_exists(self):
        for path in ("/api/secrets", "/api/secrets/status", "/api/config",
                     "/api/env", "/api/keys"):
            status, _, _ = self.call(path)
            self.assertEqual(status, 404, f"{path} must not exist")


class RoleEnforcementTests(ApiTestCase):
    def test_viewer_cannot_reach_audit(self):
        cookie, _ = self.login("viewer")
        status, payload, _ = self.call("/api/audit", cookie=cookie)
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "NOT_AUTHORIZED")

    def test_viewer_cannot_create_a_command(self):
        cookie, csrf = self.login("viewer")
        status, payload, _ = self.call(
            "/api/commands", "POST",
            {"idempotency_key": "v1", "transcript": "x", "intent": {}, "confirmed": True},
            headers={"X-DBX-CSRF": csrf}, cookie=cookie,
        )
        self.assertEqual(status, 403)

    def test_viewer_cannot_run_a_job(self):
        cookie, csrf = self.login("viewer")
        status, _, _ = self.call("/api/run-slice", "POST", {},
                                 headers={"X-DBX-CSRF": csrf}, cookie=cookie)
        self.assertEqual(status, 403)

    def test_owner_can_reach_audit(self):
        cookie, _ = self.login("ryan")
        status, payload, _ = self.call("/api/audit?limit=5", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(payload["chain_valid"])


class HoldEndpointTests(ApiTestCase):
    def test_hold_removal_endpoint_always_refuses(self):
        cookie, csrf = self.login()
        status, payload, _ = self.call(
            "/api/holds/remove", "POST", {"hold_id": "hold_section32"},
            headers={"X-DBX-CSRF": csrf}, cookie=cookie,
        )
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "HOLD_REMOVAL_FORBIDDEN")

    def test_holds_are_reported_as_not_removable(self):
        cookie, _ = self.login()
        status, payload, _ = self.call("/api/holds", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertFalse(payload["removable"])
        labels = [h["label"] for h in payload["holds"]]
        for expected in ("Horizon Section 32", "Penterra Section 20", "Penterra Section 17"):
            self.assertIn(expected, labels)


class CommandFlowTests(ApiTestCase):
    def test_command_creation_requires_confirmation(self):
        cookie, csrf = self.login()
        status, payload, _ = self.call(
            "/api/commands", "POST",
            {"idempotency_key": "nc1", "transcript": "x", "intent": {}, "confirmed": False},
            headers={"X-DBX-CSRF": csrf}, cookie=cookie,
        )
        self.assertEqual(status, 403)

    def test_duplicate_submission_returns_the_same_command(self):
        cookie, csrf = self.login()
        body = {"idempotency_key": "api-dup-1", "transcript": "check status",
                "intent": {"operation": "status.read_posture", "unresolved": []},
                "confirmed": True}
        first = self.call("/api/commands", "POST", body,
                          headers={"X-DBX-CSRF": csrf}, cookie=cookie)[1]
        second = self.call("/api/commands", "POST", body,
                           headers={"X-DBX-CSRF": csrf}, cookie=cookie)[1]
        self.assertEqual(first["command_id"], second["command_id"])

    def test_voice_intake_creates_nothing_and_requires_confirmation(self):
        cookie, csrf = self.login()
        before = self.kernel.conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
        status, payload, _ = self.call(
            "/api/voice/intake", "POST", {"transcript": "what should I do next"},
            headers={"X-DBX-CSRF": csrf}, cookie=cookie,
        )
        after = self.kernel.conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
        self.assertEqual(status, 200)
        self.assertTrue(payload["requires_confirmation"])
        self.assertEqual(before, after)
        self.assertFalse(payload["transcript"]["audio_retained"])

    def test_voice_intake_refuses_to_infer_a_missing_project(self):
        cookie, csrf = self.login()
        _, payload, _ = self.call(
            "/api/voice/intake", "POST", {"transcript": "build a draft report"},
            headers={"X-DBX-CSRF": csrf}, cookie=cookie,
        )
        self.assertTrue(payload["intent"]["unresolved"])

    def test_best_moves_withholds_the_held_scope(self):
        cookie, _ = self.login()
        _, payload, _ = self.call("/api/best-moves", cookie=cookie)
        vetoed_ids = [v["move_id"] for v in payload["vetoed"]]
        self.assertIn("mv_section32_report", vetoed_ids)
        eligible_ids = [payload["best_next_move"]["move_id"]] + \
                       [a["move_id"] for a in payload["alternatives"]]
        self.assertNotIn("mv_section32_report", eligible_ids)

    def test_posture_contains_no_absolute_paths(self):
        cookie, _ = self.login()
        _, payload, _ = self.call("/api/posture", cookie=cookie)
        blob = json.dumps(payload)
        for marker in ("C:\\", "/home/", "/root/", "canonical_folder"):
            self.assertNotIn(marker, blob)


class StaticAssetTests(ApiTestCase):
    def test_index_is_served(self):
        req = urllib.request.Request(self.base + "/")
        with urllib.request.urlopen(req, timeout=25) as res:
            body = res.read().decode()
        self.assertIn("DataBossX Command Center", body)
        self.assertIn("FOR REVIEW", body)

    def test_manifest_is_served_with_the_right_type(self):
        req = urllib.request.Request(self.base + "/manifest.webmanifest")
        with urllib.request.urlopen(req, timeout=25) as res:
            self.assertEqual(res.headers["Content-Type"], "application/manifest+json")
            manifest = json.loads(res.read())
        self.assertEqual(manifest["display"], "standalone")
        self.assertTrue(any(icon["sizes"] == "512x512" for icon in manifest["icons"]))

    def test_static_traversal_is_refused(self):
        for path in ("/../SECURITY.md", "/static/../../SECURITY.md",
                     "/%2e%2e/SECURITY.md"):
            status, _, _ = self.call(path)
            self.assertIn(status, (403, 404), f"{path} must not be served")

    def test_service_worker_is_served(self):
        req = urllib.request.Request(self.base + "/sw.js")
        with urllib.request.urlopen(req, timeout=25) as res:
            self.assertEqual(res.status, 200)


class BindingTests(unittest.TestCase):
    def test_public_binding_is_refused(self):
        from command_center.http_api import serve

        workdir = tempfile.mkdtemp(prefix="dbx-cc-bind-")
        self.addCleanup(shutil.rmtree, workdir, True)
        kernel = ControlKernel.open(os.path.join(workdir, "cc.db"))
        self.addCleanup(kernel.conn.close)
        for host in ("0.0.0.0", "192.168.1.10", ""):
            with self.assertRaises(NotAuthorized):
                serve(kernel, host=host)


if __name__ == "__main__":
    unittest.main()
